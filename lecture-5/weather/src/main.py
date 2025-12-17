import flet as ft
import requests
from datetime import datetime

def main(page: ft.Page):
    # --- アプリの基本設定 ---
    page.title = "気象庁 天気予報アプリ Pro"
    page.padding = 0  # 余白をコンテナ側で制御
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO) # テーマカラー設定

    # 状態管理用の変数
    current_area_code = None

    # --- データ取得関数群 ---

    def get_area_list():
        """地域リストを取得"""
        url = "https://www.jma.go.jp/bosai/common/const/area.json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"地域リスト取得エラー: {e}")
            return {}

    def get_weather_forecast(area_code):
        """天気予報データを取得"""
        url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"天気データ取得エラー: {e}")
            return None

    def get_icon_url(code):
        """気象庁の公式アイコンURLを生成"""
        # 気象庁のアイコンパス
        return f"https://www.jma.go.jp/bosai/forecast/img/{code}.svg"

    # --- UIコンポーネント ---

    # 1. 天気カード（1日分）
    def create_forecast_card(date_str, weather_code, weather_text, temps, pops):
        # 気温のフォーマット (例: Min 10°C / Max 20°C)
        temp_str_list = []
        if temps["min"] and temps["min"] != "-":
            temp_str_list.append(f"低: {temps['min']}℃")
        if temps["max"] and temps["max"] != "-":
            temp_str_list.append(f"高: {temps['max']}℃")
        temp_display = " / ".join(temp_str_list) if temp_str_list else "--"

        # 降水確率 (最大値を取る簡易ロジック)
        pop_display = f"降水確率: {max(pops)}%" if pops else "降水確率: --"

        return ft.Container(
            content=ft.Column([
                ft.Text(date_str, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                ft.Image(
                    src=get_icon_url(weather_code),
                    width=64,
                    height=64,
                    color=ft.Colors.GREY_800 # SVGの色調整
                ),
                ft.Text(weather_text, size=14, text_align=ft.TextAlign.CENTER, no_wrap=False),
                ft.Divider(height=10, thickness=1),
                ft.Row([
                    ft.Icon(ft.Icons.THERMOSTAT, size=16, color=ft.Colors.ORANGE),
                    ft.Text(temp_display, size=14, weight=ft.FontWeight.BOLD)
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([
                    ft.Icon(ft.Icons.WATER_DROP, size=16, color=ft.Colors.BLUE),
                    ft.Text(pop_display, size=12)
                ], alignment=ft.MainAxisAlignment.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5
            ),
            width=200,
            padding=15,
            bgcolor=ft.Colors.WHITE,
            border_radius=15,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=5,
                color=ft.Colors.BLUE_GREY_100,
                offset=ft.Offset(0, 2),
            )
        )

    # 2. メイン表示エリア
    content_area = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=20,
        controls=[
            ft.Container(
                content=ft.Text("左のメニューから地域を選択してください", size=20, color=ft.Colors.GREY),
                alignment=ft.alignment.center,
                padding=50
            )
        ]
    )

    loading_indicator = ft.ProgressRing(visible=False)

    # --- ロジック ---

    def parse_weather_data(data):
        """
        気象庁の複雑なJSON構造を解析して使いやすい辞書リストに変換する
        """
        try:
            report = data[0] # 通常の予報データ
            
            # --- timeSeries[0]: 天気と風と波 ---
            ts_weather = report["timeSeries"][0]
            time_defines = ts_weather["timeDefines"]
            area_weather = ts_weather["areas"][0] # 選択されたエリア
            weather_codes = area_weather["weatherCodes"]
            weather_texts = area_weather["weathers"]

            # --- timeSeries[1]: 降水確率 (6時間ごと) ---
            # 注: インデックスは変動する可能性があるため、本当は成分チェックが必要だが、簡易的に固定
            ts_pops = report["timeSeries"][1]
            pops_list = ts_pops["areas"][0]["pops"]
            
            # --- timeSeries[2]: 気温 (朝・日中) ---
            # 注: 地域や時間帯によってtempsが含まれる場所が変わる場合がある
            ts_temps = report["timeSeries"][2]
            temps_list = ts_temps["areas"][0]["temps"]

            forecasts = []
            
            # 降水確率と気温は配列の長さが天気と異なる場合があるため、簡易的にマッピング
            # 日付ごとに処理
            for i, time_def in enumerate(time_defines):
                dt = datetime.fromisoformat(time_def.replace("Z", "+00:00"))
                date_str = dt.strftime("%m/%d (%a)")
                
                # 気温の取得（簡易ロジック: インデックスが合わない場合はダッシュ）
                # 実際のAPIでは tempsは [明日朝最低, 明日日中最高, ...] のように並ぶ
                day_min = temps_list[i*2] if len(temps_list) > i*2 else "-"
                day_max = temps_list[i*2+1] if len(temps_list) > i*2+1 else "-"
                
                # 降水確率の取得 (1日分スライスして取得)
                # 1日あたり4つの値(0-6, 6-12, 12-18, 18-24)が入ることが多い
                pop_start = i * 4
                pop_end = pop_start + 4
                day_pops = pops_list[pop_start:pop_end] if len(pops_list) >= pop_end else []

                forecasts.append({
                    "date": date_str,
                    "code": weather_codes[i],
                    "text": weather_texts[i],
                    "temps": {"min": day_min, "max": day_max},
                    "pops": day_pops
                })
                
            return report["timeSeries"][0]["areas"][0]["area"]["name"], forecasts

        except (IndexError, KeyError) as e:
            print(f"パースエラー: {e}")
            return None, None

    def on_area_click(e):
        """地域選択時のイベントハンドラ"""
        nonlocal current_area_code
        code = e.control.data
        name = e.control.title.value
        
        # UI更新: ローディング開始
        loading_indicator.visible = True
        content_area.controls = [ft.Container(content=loading_indicator, alignment=ft.alignment.center, padding=50)]
        page.update()

        # データ取得
        raw_data = get_weather_forecast(code)
        
        if raw_data:
            area_name, forecasts = parse_weather_data(raw_data)
            
            if forecasts:
                # カード生成
                cards = []
                for f in forecasts:
                    cards.append(create_forecast_card(
                        f["date"], f["code"], f["text"], f["temps"], f["pops"]
                    ))
                
                # 表示更新
                content_area.controls = [
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{area_name} の天気予報", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO_800),
                            ft.Text("※気象庁APIデータを使用", size=12, color=ft.Colors.GREY),
                            ft.Divider(),
                            ft.Row(controls=cards, wrap=True, spacing=20, run_spacing=20),
                        ]),
                        padding=20
                    )
                ]
            else:
                content_area.controls = [ft.Text("データの解析に失敗しました。", color=ft.Colors.RED)]
        else:
            content_area.controls = [ft.Text("データの取得に失敗しました。", color=ft.Colors.RED)]

        page.update()

    # --- サイドバー作成 ---
    def build_sidebar():
        area_data = get_area_list()
        centers = area_data.get("centers", {})
        offices = area_data.get("offices", {})
        
        sidebar_items = []
        
        for center_code, center_info in centers.items():
            # 地方ごとの子供リスト（県・気象台）
            office_tiles = []
            for office_code, office_info in offices.items():
                if office_info.get("parent") == center_code:
                    office_tiles.append(
                        ft.ListTile(
                            title=ft.Text(office_info["name"], size=13),
                            leading=ft.Icon(ft.Icons.LOCATION_ON, size=16),
                            on_click=on_area_click,
                            data=office_code,
                            dense=True, # コンパクトにする
                        )
                    )
            
            if office_tiles:
                sidebar_items.append(
                    ft.ExpansionTile(
                        title=ft.Text(center_info["name"], weight=ft.FontWeight.BOLD),
                        leading=ft.Icon(ft.Icons.MAP),
                        controls=office_tiles,
                        initially_expanded=False,
                        text_color=ft.Colors.BLACK87
                    )
                )

        return ft.ListView(
            controls=sidebar_items,
            width=250,
            spacing=0,
            padding=10,
        )

    # --- レイアウト構築 ---
    sidebar = ft.Container(
        content=build_sidebar(),
        width=250,
        bgcolor=ft.Colors.GREY_100,
        border=ft.border.only(right=ft.BorderSide(1, ft.Colors.GREY_300))
    )

    layout = ft.Row(
        controls=[
            sidebar,
            content_area
        ],
        expand=True,
        spacing=0
    )

    page.add(layout)

ft.app(target=main)