# This library is derived from https://github.com/flavono123/identicon, wich is avaiable under the MIT License:
# 
# Copyright (c) 2018 Hansuk Hong
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import io
import hashlib
from PIL import Image, ImageDraw

BACKGROUND_COLOR = (0, 0, 0)

def render_identicon(code):
    hash = hashlib.md5(code.encode('utf8'))
    hex_list = hash.hexdigest()

    color = extract_color(hex_list)

    grid = build_grid(hex_list)

    flatten_grid = [e for row in grid for e in row]
    
    pixels = set_pixels(flatten_grid)

    identicon_im = draw_identicon(color, flatten_grid, pixels)

    identicon_byte_arr = io.BytesIO()
    identicon_im.save(identicon_byte_arr, format='PNG')
    identicon_byte_arr = identicon_byte_arr.getvalue()

    return identicon_byte_arr

def extract_color(hex_list):
    r,g,b = tuple(hex_list[i:i+2] for i in range(0, 2*3, 2))
    return f'#{r}{g}{b}'

def build_grid(hex_list):
    hex_list_tail = hex_list[2:]
    
    hex_half_grid = [[hex_list_tail[col:col+2] for col in range(row, row+2*3, 2)] for row in range(0, 2*3*5, 2*3)]

    hex_grid = mirror_row(hex_half_grid)
    
    int_grid = [list(map(lambda e: int(e ,base=16), row)) for row in hex_grid]

    filtered_grid = [[byte if byte%2 == 0 else 0 for byte in row] for row in int_grid]
    
    return filtered_grid

def set_pixels(flatten_grid):
    pixels = []
    for i, val in enumerate(flatten_grid):
        x = int(i%5 * 50) + 20
        y = int(i//5 * 50) + 20
        
        top_left = (x, y)
        bottom_right = (x + 50, y + 50)
        
        pixels.append([top_left, bottom_right])

    return pixels

def mirror_row(half_grid):
    opposite_half_grid = [list(reversed(row)) for row in half_grid]
    grid = [row + mirrored_row[1:] for row, mirrored_row in zip(half_grid, opposite_half_grid)]

    return grid

def draw_identicon(color, grid_list, pixels):
    identicon_im = Image.new('RGB', (50*5+20*2, 50*5+20*2), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(identicon_im)
    for grid, pixel in zip(grid_list, pixels):
        if grid != 0:
            draw.rectangle(pixel, fill=color)

    return identicon_im
