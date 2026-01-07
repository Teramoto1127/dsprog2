import flet as ft
import requests
import sqlite3
from datetime import datetime
import os

# --- データベース関連の関数 ---

DB_NAME = "weather.db"

def init_db():
    """データベースの初期化とテーブル作成"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. 地域情報テーブル (areas)
    # オプション要件: エリア情報をDBに格納する
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS areas (
        code TEXT PRIMARY KEY,
        name TEXT,
        parent_code TEXT
    )
    ''')
    
    # 2. 天気予報テーブル (forecasts)
    # 課題要件: 取得した天気情報をDBに格納する
    # 正規化: area_codeとdateで一意になるように設計
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_code TEXT,
        date_disp TEXT,
        date_iso TEXT,
        weather_code TEXT,
        weather_text TEXT,
        min_temp TEXT,
        max_temp TEXT,
        pop INTEGER,
        UNIQUE(area_code, date_iso) ON CONFLICT REPLACE
    )
    ''')
    
    conn.commit()
    conn.close()

def save_areas_to_db(areas_data):
    """地域データをDBに保存"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    centers = areas_data.get("centers", {})
    offices = areas_data.get("offices", {})
    
    # 親（地方）と子（都道府県・管区）の関係を保存
    for office_code, office_info in offices.items():
        parent = office_info.get("parent", "")
        name = office_info.get("name", "")
        cursor.execute(
            "INSERT OR REPLACE INTO areas (code, name, parent_code) VALUES (?, ?, ?)",
            (office_code, name, parent)
        )
    
    conn.commit()
    conn.close()

def save_forecasts_to_db(area_code, forecasts):
    """解析済みの予報データをDBに保存"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for f in forecasts:
        # 降水確率は最大値を保存、気温は文字列のまま保存
        pop_val = max(f["pops"]) if f["pops"] else 0
        min_t = f["temps"]["min"]
        max_t = f["temps"]["max"]
        
        cursor.execute('''
        INSERT INTO forecasts 
        (area_code, date_disp, date_iso, weather_code, weather_text, min_temp, max_temp, pop)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            area_code,
            f["date_disp"], # 表示用日付 (例: 01/07 (水))
            f["date_iso"],  # ソート/管理用日付 (例: 2026-01-07)
            f["code"],
            f["text"],
            min_t,
            max_t,
            pop_val
        ))
    
    conn.commit()
    conn.close()

def get_forecasts_from_db(area_code):
    """DBから特定の地域の予報を取得してUI用の形式で返す"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # カラム名でアクセスできるようにする
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM forecasts WHERE area_code = ? ORDER BY date_iso ASC",
        (area_code,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "date": row["date_disp"],
            "code": row["weather_code"],
            "text": row["weather_text"],
            "temps": {"min": row["min_temp"], "max": row["max_temp"]},
            "pop_display": row["pop"] # 保存時にmaxを取っているため単一の値
        })
    return results

def get_area_name_from_db(area_code):
    """DBから地域名を取得"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM areas WHERE code = ?", (area_code,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "不明な地域"


# --- メインアプリ ---

def main(page: ft.Page):
    # アプリ起動時にDB初期化
    init_db()

    # --- アプリの基本設定 ---
    page.title = "気象庁 天気予報アプリ Pro (DB版)"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)

    # 状態管理用の変数
    current_area_code = None

    # --- データ取得関数群 (API) ---

    def fetch_area_list():
        """APIから地域リストを取得しDBに保存"""
        url = "https://www.jma.go.jp/bosai/common/const/area.json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            # 取得したらすぐにDBへ保存
            save_areas_to_db(data)
            return data
        except Exception as e:
            print(f"地域リスト取得エラー: {e}")
            return {}

    def fetch_weather_forecast(area_code):
        """APIから天気予報データを取得"""
        url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"天気データ取得エラー: {e}")
            return None

    def get_icon_url(code):
        return f"https://www.jma.go.jp/bosai/forecast/img/{code}.svg"

    # --- UIコンポーネント ---

    def create_forecast_card_from_db_data(data):
        """DBから取得したデータを元にカードを作成"""
        # 気温表示
        temp_str_list = []
        if data["temps"]["min"] and data["temps"]["min"] != "-":
            temp_str_list.append(f"低:{data['temps']['min']}℃")
        if data["temps"]["max"] and data["temps"]["max"] != "-":
            temp_str_list.append(f"高:{data['temps']['max']}℃")
        temp_display = " / ".join(temp_str_list) if temp_str_list else "--"

        # 降水確率
        pop_display = f"降水確率: {data['pop_display']}%"

        return ft.Container(
            content=ft.Column([
                ft.Text(data["date"], size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                ft.Image(
                    src=get_icon_url(data["code"]),
                    width=64,
                    height=64,
                    color=ft.Colors.GREY_800
                ),
                ft.Text(data["text"], size=14, text_align=ft.TextAlign.CENTER, no_wrap=False),
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

    def parse_weather_data_for_db(data):
        """APIの生データをDB保存しやすい形式に整形する"""
        try:
            report = data[0]
            ts_weather = report["timeSeries"][0]
            time_defines = ts_weather["timeDefines"]
            area_weather = ts_weather["areas"][0]
            weather_codes = area_weather["weatherCodes"]
            weather_texts = area_weather["weathers"]

            ts_pops = report["timeSeries"][1]
            pops_list = ts_pops["areas"][0]["pops"]
            
            ts_temps = report["timeSeries"][2]
            temps_list = ts_temps["areas"][0]["temps"]

            parsed_list = []
            
            for i, time_def in enumerate(time_defines):
                dt = datetime.fromisoformat(time_def.replace("Z", "+00:00"))
                date_disp = dt.strftime("%m/%d (%a)")
                date_iso = dt.strftime("%Y-%m-%d") # DBでのソート用
                
                day_min = temps_list[i*2] if len(temps_list) > i*2 else "-"
                day_max = temps_list[i*2+1] if len(temps_list) > i*2+1 else "-"
                
                pop_start = i * 4
                pop_end = pop_start + 4
                day_pops = pops_list[pop_start:pop_end] if len(pops_list) >= pop_end else []
                # 整数型に変換しておく
                day_pops_int = [int(p) for p in day_pops if p.isdigit()]

                parsed_list.append({
                    "date_disp": date_disp,
                    "date_iso": date_iso,
                    "code": weather_codes[i],
                    "text": weather_texts[i],
                    "temps": {"min": day_min, "max": day_max},
                    "pops": day_pops_int
                })
                
            return parsed_list

        except (IndexError, KeyError) as e:
            print(f"パースエラー: {e}")
            return []

    def on_area_click(e):
        """地域選択時のイベントハンドラ"""
        nonlocal current_area_code
        code = e.control.data
        # 地域名はDBから取得することも可能だが、ここではクリックイベントから取るのが早い
        # しかし課題の趣旨に沿い、後でDBからArea名を取る形にするためここではcodeのみ使う
        
        loading_indicator.visible = True
        content_area.controls = [ft.Container(content=loading_indicator, alignment=ft.alignment.center, padding=50)]
        page.update()

        # 1. APIからデータ取得
        raw_data = fetch_weather_forecast(code)
        
        if raw_data:
            # 2. データをパースしてリスト化
            parsed_data = parse_weather_data_for_db(raw_data)
            
            if parsed_data:
                # 3. 【重要】パースしたデータをDBに保存 (課題要件)
                save_forecasts_to_db(code, parsed_data)
                
                # 4. 【重要】表示用データはDBから取得する (課題要件)
                db_forecasts = get_forecasts_from_db(code)
                area_name = get_area_name_from_db(code) # DBから地域名取得

                # カード生成
                cards = []
                for f in db_forecasts:
                    cards.append(create_forecast_card_from_db_data(f))
                
                # 表示更新
                content_area.controls = [
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{area_name} の天気予報", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO_800),
                            ft.Text("※気象庁API -> SQLite DB -> 表示", size=12, color=ft.Colors.GREY), # フロー確認用テキスト
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
        # APIから地域リストを取得し、内部でDBに保存している
        area_data = fetch_area_list()
        
        centers = area_data.get("centers", {})
        offices = area_data.get("offices", {})
        
        sidebar_items = []
        
        for center_code, center_info in centers.items():
            office_tiles = []
            for office_code, office_info in offices.items():
                if office_info.get("parent") == center_code:
                    office_tiles.append(
                        ft.ListTile(
                            title=ft.Text(office_info["name"], size=13),
                            leading=ft.Icon(ft.Icons.LOCATION_ON, size=16),
                            on_click=on_area_click,
                            data=office_code,
                            dense=True,
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