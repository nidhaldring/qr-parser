import os
import json
import numpy as np

from typing import TypedDict
from PIL import Image
from io import BytesIO
from fastapi import FastAPI, UploadFile
from qreader import QReader

from mistralai import Mistral


api_key = os.environ["MISTRAL_API_KEY"]

app = FastAPI()
qreader = QReader()
mistral_client = Mistral(api_key=api_key)


class ParseQrResult(TypedDict):
    fullName: str
    email: str
    phone: str
    address: str


@app.post("/qr")
async def parse_qr(file: UploadFile):
    contents = np.array(Image.open(BytesIO(await file.read())).convert("RGB"))
    vcard = str(qreader.detect_and_decode(image=contents))

    try:
        resp = vcard_to_json(vcard)
        json_result = str(resp.choices[0].message.content)[7:-3]
        result = json.loads(json_result)

        print(result)
        return result

    except:
        return {"fullName": "", "email": "", "phone": "", "address": ""}


def vcard_to_json(s: str):
    parsing_prompt = f"""
        YOUR MISSION:
        You are a data parser. Convert the following vCard text content into a JSON object. The JSON should include only these fields:

        fullName: the contact's full name

        email: the primary email address

        phone: the primary telephone number

        address: the full formatted address as a single string

        Note: Only include the json without anything else!

        If any field is missing, set its value to empty string. Here's the vCard content: 
        Phone should include +then country code then number. without  () or -.
        Make sure email is lowercase

        IMPORTANT: do not infer any values. If a field is not present in the vCard, set its value to empty string.
        {s}
    """

    chat_response = mistral_client.chat.complete(
        model="mistral-large-latest",
        messages=[
            {
                "role": "user",
                "content": parsing_prompt,
            },
        ],
    )

    return chat_response
