import flet as ft
import math

class CalcButton(ft.ElevatedButton):
    def __init__(self, text, button_clicked, expand=1):
        super().__init__()
        self.text = text
        self.expand = expand
        self.on_click = button_clicked
        self.data = text

class DigitButton(CalcButton):
    def __init__(self, text, button_clicked, expand=1):
        CalcButton.__init__(self, text, button_clicked, expand)
        self.bgcolor = ft.Colors.WHITE24
        self.color = ft.Colors.WHITE

class ActionButton(CalcButton):
    def __init__(self, text, button_clicked):
        CalcButton.__init__(self, text, button_clicked)
        self.bgcolor = ft.Colors.ORANGE
        self.color = ft.Colors.WHITE

class ExtraActionButton(CalcButton):
    def __init__(self, text, button_clicked):
        CalcButton.__init__(self, text, button_clicked)
        self.bgcolor = ft.Colors.BLUE_GREY_100
        self.color = ft.Colors.BLACK

# 新しく追加した科学計算用ボタンクラス
class ScientificButton(CalcButton):
    def __init__(self, text, button_clicked):
        CalcButton.__init__(self, text, button_clicked)
        self.bgcolor = ft.Colors.INDIGO_400 # 色を区別
        self.color = ft.Colors.WHITE

class CalculatorApp(ft.Container):
    def __init__(self):
        super().__init__()
        self.reset()

        self.result = ft.Text(value="0", color=ft.Colors.WHITE, size=20)
        # レイアウト変更のため幅を拡張 (350 -> 450)
        self.width = 450 
        self.bgcolor = ft.Colors.BLACK
        self.border_radius = ft.border_radius.all(20)
        self.padding = 20
        self.content = ft.Column(
            controls=[
                ft.Row(controls=[self.result], alignment="end"),
                ft.Row(
                    controls=[
                        # べき乗 (二項演算)
                        ScientificButton(text="^", button_clicked=self.button_clicked),
                        ExtraActionButton(text="AC", button_clicked=self.button_clicked),
                        ExtraActionButton(text="+/-", button_clicked=self.button_clicked),
                        ExtraActionButton(text="%", button_clicked=self.button_clicked),
                        ActionButton(text="/", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        # sin (単項演算)
                        ScientificButton(text="sin", button_clicked=self.button_clicked),
                        DigitButton(text="7", button_clicked=self.button_clicked),
                        DigitButton(text="8", button_clicked=self.button_clicked),
                        DigitButton(text="9", button_clicked=self.button_clicked),
                        ActionButton(text="*", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        # cos (単項演算)
                        ScientificButton(text="cos", button_clicked=self.button_clicked),
                        DigitButton(text="4", button_clicked=self.button_clicked),
                        DigitButton(text="5", button_clicked=self.button_clicked),
                        DigitButton(text="6", button_clicked=self.button_clicked),
                        ActionButton(text="-", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        # tan (単項演算)
                        ScientificButton(text="tan", button_clicked=self.button_clicked),
                        DigitButton(text="1", button_clicked=self.button_clicked),
                        DigitButton(text="2", button_clicked=self.button_clicked),
                        DigitButton(text="3", button_clicked=self.button_clicked),
                        ActionButton(text="+", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        # log, sqrt, pi (その他)
                        ScientificButton(text="log", button_clicked=self.button_clicked),
                        DigitButton(text="0", button_clicked=self.button_clicked),
                        ScientificButton(text="π", button_clicked=self.button_clicked), # 0の横に追加
                        DigitButton(text=".", button_clicked=self.button_clicked),
                        ActionButton(text="=", button_clicked=self.button_clicked),
                    ]
                ),
                # もう一行追加して充実させる
                 ft.Row(
                    controls=[
                        ScientificButton(text="√", button_clicked=self.button_clicked),
                        # 空白を埋めるためのプレースホルダーまたは将来の拡張用
                        ft.Container(expand=4) 
                    ]
                ),
            ]
        )

    def button_clicked(self, e):
        data = e.control.data
        print(f"Button clicked with data = {data}")
        
        # エラー処理後の復帰
        if self.result.value == "Error":
             self.result.value = "0"
             self.reset()

        if data == "AC":
            self.result.value = "0"
            self.reset()

        elif data in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "."):
            if self.result.value == "0" or self.new_operand == True:
                self.result.value = data
                self.new_operand = False
            else:
                self.result.value = self.result.value + data

        # 二項演算子 (+, -, *, /, ^)
        elif data in ("+", "-", "*", "/", "^"):
            self.result.value = self.calculate(self.operand1, float(self.result.value), self.operator)
            self.operator = data
            if self.result.value == "Error":
                self.operand1 = "0"
            else:
                self.operand1 = float(self.result.value)
            self.new_operand = True

        elif data in ("="):
            self.result.value = self.calculate(self.operand1, float(self.result.value), self.operator)
            self.reset()

        elif data in ("%"):
            self.result.value = float(self.result.value) / 100
            self.reset()

        elif data in ("+/-"):
            if float(self.result.value) > 0:
                self.result.value = "-" + str(self.result.value)
            elif float(self.result.value) < 0:
                self.result.value = str(self.format_number(abs(float(self.result.value))))

        # --- 科学計算ロジック (単項演算) ---
        elif data in ("sin", "cos", "tan", "log", "√"):
            val = float(self.result.value)
            res = 0
            try:
                if data == "sin":
                    res = math.sin(val) # ラジアン入力
                elif data == "cos":
                    res = math.cos(val)
                elif data == "tan":
                    res = math.tan(val)
                elif data == "log":
                    res = math.log(val) # 自然対数
                elif data == "√":
                    res = math.sqrt(val)
                
                self.result.value = str(self.format_number(res))
                self.new_operand = True # 計算後は次の入力で数字をリセットする
            except ValueError:
                self.result.value = "Error"

        # --- 定数 ---
        elif data == "π":
            self.result.value = str(math.pi)
            self.new_operand = True

        self.update()

    def format_number(self, num):
        try:
            if num % 1 == 0:
                return int(num)
            else:
                # 小数点以下が長すぎる場合に丸める（例: 10桁）
                return round(num, 10)
        except:
            return num

    def calculate(self, operand1, operand2, operator):
        try:
            if operator == "+":
                return self.format_number(operand1 + operand2)
            elif operator == "-":
                return self.format_number(operand1 - operand2)
            elif operator == "*":
                return self.format_number(operand1 * operand2)
            elif operator == "/":
                if operand2 == 0:
                    return "Error"
                else:
                    return self.format_number(operand1 / operand2)
            # べき乗の計算を追加
            elif operator == "^":
                return self.format_number(math.pow(operand1, operand2))
        except:
            return "Error"

    def reset(self):
        self.operator = "+"
        self.operand1 = 0
        self.new_operand = True

def main(page: ft.Page):
    page.title = "Scientific Calculator"
    # ウィンドウサイズも少し大きくしておきます
    page.window_width = 500
    page.window_height = 600
    calc = CalculatorApp()
    page.add(calc)

ft.app(main)