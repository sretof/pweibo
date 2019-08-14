import pytesseract
from PIL import Image
from aip import AipOcr

image = Image.open('F:\\image.jpg')
code = pytesseract.image_to_string(image)
print(code)


APP_ID = '17014580'
API_KEY = 'CB0cZSAnGgeNUKs9bL9FlCZ6'
SECRET_KEY = 'G8WtGq9GZsH8CtjRtLfgF0t5evoTeL3C'

client = AipOcr(APP_ID, API_KEY, SECRET_KEY)


def get_file_content(filePath):
    with open(filePath, 'rb') as fp:
        return fp.read()

imageb = get_file_content('F:\\image.jpg')

options = {}
options["language_type"] = "ENG"
rtxt = client.basicGeneral(imageb,options)
print(rtxt)

rtxt2 = client.basicAccurate(imageb,options)
print(rtxt2)

rtxt3 = client.webImage(imageb,options)
print(rtxt3)
