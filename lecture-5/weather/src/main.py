import flet as ft
import requests
import sqlite3
from datetime import datetime
import os

# --- 定数 ---
DB_NAME = "weather.db"
THEME_COLOR = ft.Colors.INDIGO

# ==========================================
# 1. データベース管理 (Model層)
# ==========================================

def init_db():
    """データベースと全テーブルの初期化"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # (1) 地域マスタ
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS areas (
        code TEXT PRIMARY KEY,
        name TEXT,
        parent_code TEXT
    )
    ''')
    
    # (2) 天気予報データ (ユニーク制約付き)
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

    # (3) 【新機能】お気に入りテーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_code TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def save_areas_to_db(areas_data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    centers = areas_data.get("centers", {})
    offices = areas_data.get("offices", {})
    
    for office_code, office_info in offices.items():
        parent = office_info.get("parent", "")
        name = office_info.get("name", "")
        cursor.execute("INSERT OR REPLACE INTO areas (code, name, parent_code) VALUES (?, ?, ?)", (office_code, name, parent))
    conn.commit()
    conn.close()

def save_forecasts_to_db(area_code, forecasts):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for f in forecasts:
        pop_val = max(f["pops"]) if f["pops"] else 0
        cursor.execute('''
        INSERT INTO forecasts (area_code, date_disp, date_iso, weather_code, weather_text, min_temp, max_temp, pop)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (area_code, f["date_disp"], f["date_iso"], f["code"], f["text"], f["temps"]["min"], f["temps"]["max"], pop_val))
    conn.commit()
    conn.close()

def get_forecasts_from_db(area_code):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM forecasts WHERE area_code = ? ORDER BY date_iso ASC", (area_code,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_area_name(area_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM areas WHERE code = ?", (area_code,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "不明な地域"

# --- お気に入り関連のDB操作 ---
def toggle_favorite_db(area_code):
    """お気に入りの登録/解除を切り替える"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 既に登録されているか確認
    cursor.execute("SELECT id FROM favorites WHERE area_code = ?", (area_code,))
    exists = cursor.fetchone()
    
    is_fav = False
    if exists:
        # 解除 (DELETE)
        cursor.execute("DELETE FROM favorites WHERE area_code = ?", (area_code,))
        is_fav = False
    else:
        # 登録 (INSERT)
        cursor.execute("INSERT INTO favorites (area_code) VALUES (?)", (area_code,))
        is_fav = True
        
    conn.commit()
    conn.close()
    return is_fav

def check_is_favorite(area_code):
    """お気に入り状態を確認"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM favorites WHERE area_code = ?", (area_code,))
    exists = cursor.fetchone()
    conn.close()
    return True if exists else False


# ==========================================
# 2. API通信 & データ整形 (Controller層)
# ==========================================

def fetch_area_list():
    try:
        url = "https://www.jma.go.jp/bosai/common/const/area.json"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        save_areas_to_db(data) # DB保存
        return data
    except Exception as e:
        print(f"Area Error: {e}")
        return {}

def fetch_weather_forecast(area_code):
    try:
        url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Weather Error: {e}")
        return None

def parse_weather_data(data):
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

        parsed = []
        for i, time_def in enumerate(time_defines):
            dt = datetime.fromisoformat(time_def.replace("Z", "+00:00"))
            date_disp = dt.strftime("%m/%d (%a)")
            date_iso = dt.strftime("%Y-%m-%d")
            
            day_min = temps_list[i*2] if len(temps_list) > i*2 else "-"
            day_max = temps_list[i*2+1] if len(temps_list) > i*2+1 else "-"
            
            pop_start = i * 4
            pop_end = pop_start + 4
            day_pops = pops_list[pop_start:pop_end] if len(pops_list) >= pop_end else []
            day_pops_int = [int(p) for p in day_pops if p.isdigit()]

            parsed.append({
                "date_disp": date_disp,
                "date_iso": date_iso,
                "code": weather_codes[i],
                "text": weather_texts[i],
                "temps": {"min": day_min, "max": day_max},
                "pops": day_pops_int
            })
        return parsed
    except Exception:
        return []


# ==========================================
# 3. UI表示 (View層)
# ==========================================

def main(page: ft.Page):
    init_db() # 起動時にDB準備

    page.title = "天気予報アプリ Pro (DB完全版)"
    page.theme = ft.Theme(color_scheme_seed=THEME_COLOR)
    page.padding = 0
    
    # 状態変数
    current_area_code = None

    # --- UI部品: 天気カード ---
    def create_card(row_data):
        temp_str = []
        if row_data["min_temp"] != "-": temp_str.append(f"低:{row_data['min_temp']}℃")
        if row_data["max_temp"] != "-": temp_str.append(f"高:{row_data['max_temp']}℃")
        temp_disp = " / ".join(temp_str) if temp_str else "--"
        
        img_url = f"https://www.jma.go.jp/bosai/forecast/img/{row_data['weather_code']}.svg"
        
        return ft.Container(
            content=ft.Column([
                ft.Text(row_data["date_disp"], weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                ft.Image(src=img_url, width=64, height=64, color=ft.Colors.GREY_800),
                ft.Text(row_data["weather_text"], size=13, text_align=ft.TextAlign.CENTER),
                ft.Divider(height=5),
                ft.Row([ft.Icon(ft.Icons.THERMOSTAT, size=16, color=ft.Colors.ORANGE), ft.Text(temp_disp, size=13, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([ft.Icon(ft.Icons.WATER_DROP, size=16, color=ft.Colors.BLUE), ft.Text(f"{row_data['pop']}%", size=12)], alignment=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3),
            width=180, padding=15, bgcolor=ft.Colors.WHITE, border_radius=15,
            shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.BLUE_GREY_100, offset=ft.Offset(0, 2))
        )

    # --- UI部品: DB確認画面 ---
    def show_db_data(e):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # forecastsテーブル
        cursor.execute("SELECT area_code, date_disp, weather_text, pop FROM forecasts ORDER BY id DESC LIMIT 10")
        f_rows = cursor.fetchall()
        
        # favoritesテーブル
        cursor.execute("SELECT id, area_code, created_at FROM favorites")
        fav_rows = cursor.fetchall()
        
        conn.close()

        # テーブル作成ヘルパー
        def make_dt(cols, data_rows):
            return ft.DataTable(
                columns=[ft.DataColumn(ft.Text(c)) for c in cols],
                rows=[ft.DataRow(cells=[ft.DataCell(ft.Text(str(val))) for val in row]) for row in data_rows],
                border=ft.border.all(1, ft.Colors.GREY_300)
            )

        content_area.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Text("データベース内部データ (確認用)", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text("Forecasts テーブル (最新10件)", weight=ft.FontWeight.BOLD),
                    ft.Row([make_dt(["Code", "日付", "天気", "降水確率"], f_rows)], scroll=ft.ScrollMode.ALWAYS),
                    ft.Divider(),
                    ft.Text("Favorites テーブル (全件)", weight=ft.FontWeight.BOLD),
                    ft.Row([make_dt(["ID", "Code", "登録日時"], fav_rows)], scroll=ft.ScrollMode.ALWAYS),
                    ft.ElevatedButton("天気画面に戻る", on_click=lambda _: display_weather(current_area_code))
                ], scroll=ft.ScrollMode.AUTO),
                padding=20
            )
        ]
        page.update()

    # --- お気に入りボタン処理 ---
    fav_icon_button = ft.IconButton(
        icon=ft.Icons.STAR_BORDER,
        icon_color=ft.Colors.YELLOW_800,
        icon_size=30,
        tooltip="お気に入り登録/解除",
        visible=False
    )

    def on_fav_click(e):
        if current_area_code:
            new_state = toggle_favorite_db(current_area_code)
            fav_icon_button.icon = ft.Icons.STAR if new_state else ft.Icons.STAR_BORDER
            # スナックバーで通知
            msg = "お気に入りに登録しました！" if new_state else "お気に入りを解除しました"
            page.snack_bar = ft.SnackBar(ft.Text(msg))
            page.snack_bar.open = True
            page.update()

    fav_icon_button.on_click = on_fav_click

    # --- メイン天気表示ロジック ---
    def display_weather(code):
        nonlocal current_area_code
        current_area_code = code
        
        # 1. ヘッダー情報の準備
        area_name = get_area_name(code)
        is_fav = check_is_favorite(code)
        
        fav_icon_button.visible = True
        fav_icon_button.icon = ft.Icons.STAR if is_fav else ft.Icons.STAR_BORDER

        # 2. DBから予報データ取得
        db_rows = get_forecasts_from_db(code)
        cards = [create_card(row) for row in db_rows]

        content_area.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"{area_name} の天気", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.INDIGO_800),
                        fav_icon_button
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text("※気象庁API -> DB(forecasts) -> 表示", size=12, color=ft.Colors.GREY),
                    ft.Divider(),
                    ft.Row(controls=cards, wrap=True, spacing=15, run_spacing=15),
                    ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
                    ft.ElevatedButton("DBの中身を確認する", icon=ft.Icons.STORAGE, on_click=show_db_data)
                ]),
                padding=20
            )
        ]
        page.update()

    # --- 地域選択イベント ---
    loading = ft.ProgressRing(visible=False)

    def on_area_click(e):
        code = e.control.data
        loading.visible = True
        content_area.controls = [ft.Container(content=loading, alignment=ft.alignment.center, padding=50)]
        page.update()

        # API取得 -> DB保存
        raw_data = fetch_weather_forecast(code)
        if raw_data:
            parsed = parse_weather_data(raw_data)
            if parsed:
                save_forecasts_to_db(code, parsed)
                display_weather(code)
            else:
                content_area.controls = [ft.Text("データ解析エラー")]
        else:
            content_area.controls = [ft.Text("データ取得エラー")]
        
        page.update()

    # --- サイドバー構築 ---
    def build_sidebar():
        area_data = fetch_area_list()
        centers = area_data.get("centers", {})
        offices = area_data.get("offices", {})
        items = []
        for c_code, c_info in centers.items():
            children = []
            for o_code, o_info in offices.items():
                if o_info.get("parent") == c_code:
                    children.append(ft.ListTile(title=ft.Text(o_info["name"], size=13), leading=ft.Icon(ft.Icons.LOCATION_ON, size=16), on_click=on_area_click, data=o_code, dense=True))
            if children:
                items.append(ft.ExpansionTile(title=ft.Text(c_info["name"], weight=ft.FontWeight.BOLD), leading=ft.Icon(ft.Icons.MAP), controls=children, text_color=ft.Colors.BLACK87))
        return ft.ListView(controls=items, spacing=0, padding=10)

    # --- レイアウト ---
    content_area = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, controls=[
        ft.Container(content=ft.Text("地域を選択してください", size=20, color=ft.Colors.GREY), alignment=ft.alignment.center, padding=50)
    ])

    layout = ft.Row([
        ft.Container(content=build_sidebar(), width=250, bgcolor=ft.Colors.GREY_100, border=ft.border.only(right=ft.BorderSide(1, ft.Colors.GREY_300))),
        content_area
    ], expand=True, spacing=0)

    page.add(layout)

ft.app(target=main)