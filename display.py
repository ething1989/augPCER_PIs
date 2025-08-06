import ST7735
from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoMedium as UserFont

class Display:
    def __init__(self):
        self.st7735 = ST7735.ST7735(
            port=0, cs=1, dc="GPIO9", backlight="GPIO12",
            rotation=270, spi_speed_hz=10_000_000
        )
        self.st7735.set_backlight(0)

        self.WIDTH, self.HEIGHT = self.st7735.width, self.st7735.height
        self.font_large = ImageFont.truetype(UserFont, 20)
        self.font_small = ImageFont.truetype(UserFont, 10)

        self.img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=0)
        self.draw = ImageDraw.Draw(self.img)

        self.left_lines = []
        self.right_lines = []
        self.max_lines = self.HEIGHT // 10
        self.column_width = (self.WIDTH * 2) // 3

        self.on = False

    def turn_on(self):
        if not self.on:
            self.st7735.begin()
            self.clear()
            self.st7735.set_backlight(1)
            self.on = True

    def turn_off(self):
        if self.on:
            self.st7735.set_backlight(0)
            self.on = False

    def clear(self):
        self.draw.rectangle((0, 0, self.WIDTH, self.HEIGHT), fill=0)
        self.st7735.display(self.img)

    def print_left(self, new_line, stdout=True):
        if stdout:
            print(new_line)

        self.left_lines.append(new_line)
        self.left_lines = self.left_lines[-self.max_lines:]

        self.update_display_left()
    
    def clear_left(self):
        self.left_lines = []

    def print_right(self, new_line, stdout=True):
        if stdout:
            print(new_line)

        self.right_lines.append(new_line)
        self.right_lines = self.right_lines[-self.max_lines:]

        self.update_display_right()

    def clear_right(self):
        self.right_lines = []

    def update_display_left(self):
        self.draw.rectangle((0, 0, self.column_width, self.HEIGHT), fill=0)
    
        # Draw left column with truncation
        for i, line in enumerate(self.left_lines):
            truncated_line = self.truncate_text(line, self.column_width)
            self.draw.text((2, i * 10), truncated_line, font=self.font_small, fill=(255, 255, 255))
    
        self.st7735.display(self.img)

    def update_display_right(self):
        self.draw.rectangle((self.column_width, 0, self.WIDTH, self.HEIGHT), fill=0)
    
        # Draw right column with truncation
        for i, line in enumerate(self.right_lines):
            truncated_line = self.truncate_text(line, self.column_width - 4)  # Account for padding
            self.draw.text((self.column_width + 2, i * 10), truncated_line, font=self.font_small, fill=(255, 255, 255))
    
        self.st7735.display(self.img)

    def truncate_text(self, text, max_width):
        while len(text) > 0 and self.draw.textlength(text, font=self.font_small) > max_width:
            text = text[:-1]
        return text
