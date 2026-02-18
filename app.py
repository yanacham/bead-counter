import flet as ft
import cv2
import numpy as np
import base64

# --- グローバル変数（元の画像を覚えておくため） ---
original_cv_image = None

# --- 起動時の透明ダミー画像 ---
TRANSPARENT_IMG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

def main(page: ft.Page):
    page.title = "Bead Counter Pro"
    page.window_width = 390
    page.window_height = 844
    page.bgcolor = "white"
    page.scroll = "auto"

    # --- OpenCVの画像をFletで表示できるBase64文字に変換する関数 ---
    def cv_to_base64(cv_img):
        _, buffer = cv2.imencode(".png", cv_img)
        return base64.b64encode(buffer).decode("utf-8")

    # --- UIパーツ ---
    # 画像パーツ（src_base64を使って直接データを流し込みます）
    img = ft.Image(src_base64=TRANSPARENT_IMG, width=300, height=400, fit=ft.ImageFit.CONTAIN)
    result_text = ft.Text("画像を選択してください", color="black", size=20, weight="bold")

    # --- スライダーUI（初期値） ---
    slider_sensitivity = ft.Slider(min=10, max=60, divisions=50, value=15, label="感度: {value}")
    slider_dist = ft.Slider(min=10, max=100, divisions=90, value=15, label="距離: {value}")
    slider_visual_r = ft.Slider(min=5, max=50, divisions=45, value=20, label="見た目サイズ: {value}")
    slider_min_r = ft.Slider(min=5, max=50, divisions=45, value=10, label="最小半径: {value}")
    slider_max_r = ft.Slider(min=10, max=80, divisions=70, value=30, label="最大半径: {value}")

    # --- 重なり除去ロジック ---
    def remove_overlaps(points, radius):
        if not points: return []
        min_distance_sq = (radius * 1.8) ** 2
        kept_points = []
        for pt in points:
            is_overlapping = False
            for kept in kept_points:
                dist_sq = (pt[0] - kept[0])**2 + (pt[1] - kept[1])**2
                if dist_sq < min_distance_sq:
                    is_overlapping = True
                    break
            if not is_overlapping:
                kept_points.append(pt)
        return kept_points

    # --- メインの検出処理関数（スライダーを動かすたびに呼ばれる） ---
    def run_detection(e=None):
        global original_cv_image
        
        # 画像がまだ読み込まれていなければ何もしない
        if original_cv_image is None:
            return

        result_text.value = "計算中..."
        result_text.update()

        # 1. 元の画像をコピーして使う（元の画像を汚さないため）
        process_img = original_cv_image.copy()

        # 2. スライダーの値を取得
        p_param2 = int(slider_sensitivity.value)
        p_min_dist = int(slider_dist.value)
        p_visual_r = int(slider_visual_r.value)
        p_min_r = int(slider_min_r.value)
        p_max_r = int(slider_max_r.value)

        # 3. 画像処理（グレー化 -> Hough変換）
        gray = cv2.cvtColor(process_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)

        circles = cv2.HoughCircles(
            gray, 
            cv2.HOUGH_GRADIENT, 
            dp=1, 
            minDist=max(1, p_min_dist),
            param1=50, 
            param2=max(1, p_param2),
            minRadius=max(1, p_min_r),
            maxRadius=max(1, p_max_r)
        )

        detected_points = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                detected_points.append([int(i[0]), int(i[1])])

        # 4. 重なり除去
        final_points = remove_overlaps(detected_points, p_visual_r)

        # 5. 描画（コピーした画像に描く）
        for i, pt in enumerate(final_points):
            cv2.circle(process_img, (pt[0], pt[1]), p_visual_r, (0, 255, 0), 2)
            cv2.circle(process_img, (pt[0], pt[1]), 2, (0, 0, 255), -1)
            # 文字描画
            text = str(i + 1)
            font_scale = max(0.3, p_visual_r / 45.0)
            (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
            cv2.putText(process_img, text, (pt[0]-w//2, pt[1]+h//2), 
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 255), 1, cv2.LINE_AA)

        # 6. 画像をBase64に変換して表示更新
        new_base64 = cv_to_base64(process_img)
        img.src_base64 = new_base64
        img.update()

        # 7. テキスト更新
        result_text.value = f"検出数: {len(final_points)} 個"
        result_text.color = "red"
        result_text.update()

    # --- スライダーにイベントを登録 ---
    # on_change にすることで、ドラッグ中もリアルタイムに反応します
    slider_sensitivity.on_change = run_detection
    slider_dist.on_change = run_detection
    slider_visual_r.on_change = run_detection
    slider_min_r.on_change = run_detection
    slider_max_r.on_change = run_detection

    # --- ファイル選択時の処理 ---
    def on_file_picked(e):
        global original_cv_image
        if e.files:
            file_path = e.files[0].path
            
            # 日本語パス対策で numpy から読み込む
            try:
                n = np.fromfile(file_path, np.uint8)
                original_cv_image = cv2.imdecode(n, cv2.IMREAD_COLOR)
            except Exception as err:
                result_text.value = "読み込みエラー"
                result_text.update()
                return

            if original_cv_image is None:
                result_text.value = "画像として開けませんでした"
                result_text.update()
                return

            # まずはそのまま表示
            img.src_base64 = cv_to_base64(original_cv_image)
            img.update()
            
            result_text.value = "準備OK！カウントボタンを押すか、スライダーを動かしてください"
            result_text.color = "blue"
            result_text.update()

    # FilePicker設定
    file_picker = ft.FilePicker()
    file_picker.on_result = on_file_picked
    page.overlay.append(file_picker)

    # --- 画面レイアウト ---
    page.add(
        ft.Column(
            [
                ft.Text("Bead Counter Pro", size=30, weight="bold", color="blue"),
                
                ft.Container(
                    content=img, 
                    border=ft.border.all(1, "grey"), 
                    border_radius=10
                ),
                
                ft.Row(
                    [
                        ft.ElevatedButton(
                            text="画像を選ぶ",
                            icon="camera_alt", 
                            on_click=lambda _: file_picker.pick_files(),
                            bgcolor="blue", 
                            color="white"
                        ),
                        ft.ElevatedButton(
                            text="再計算",
                            icon="refresh", 
                            on_click=run_detection,
                            bgcolor="green", 
                            color="white"
                        ),
                    ],
                    alignment="center"
                ),
                
                result_text,

                # 折りたたみ式の調整パネル
                ft.ExpansionTile(
                    title=ft.Text("▼ 調整パネル (リアルタイム反映)"),
                    subtitle=ft.Text("スライダーを動かすと結果が変わります"),
                    controls=[
                        ft.Text("感度 (小さいほど検出しやすい)"),
                        slider_sensitivity,
                        ft.Text("ビーズ間の距離"),
                        slider_dist,
                        ft.Text("円の見た目サイズ"),
                        slider_visual_r,
                        ft.Text("最小半径"),
                        slider_min_r,
                        ft.Text("最大半径"),
                        slider_max_r,
                    ],
                    initially_expanded=True # 最初から開いておく
                )
            ],
            alignment="center",
            horizontal_alignment="center",
            spacing=10
        )
    )

if __name__ == "__main__":
    ft.app(target=main)