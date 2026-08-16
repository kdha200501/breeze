import sys
from PIL import Image
name = sys.argv[1] if len(sys.argv) > 1 else 'zoomInCursor.png'
im = Image.open(name).convert('RGBA')
px = im.load()
w,h = im.size
print(w,h)
for y in range(h):
    row=''
    for x in range(w):
        r,g,b,a = px[x,y]
        if a<128: row+='.'
        else: row += '#' if (r+g+b)<300 else 'o'
    print(row)
