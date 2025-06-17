import os
import json
import numpy as np
import vobject

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
    vcard_tuple = qreader.detect_and_decode(image=contents)

    try:
        print(vcard_tuple)
        if len(vcard_tuple) == 0:
            raise Exception("vcard empty")

        vcard = str(vcard_tuple[0])
        parsed_vcard = parse_vcard(vcard) if len(vcard_tuple) == 1 else None
        if parsed_vcard:
            return parsed_vcard

        print("Parsing manually failed !")
        print("Got vcard ", vcard)
        print("Will try Ai now")

        # else try with ai
        resp = vcard_to_json(str(vcard_tuple))
        json_result = str(resp.choices[0].message.content)[7:-3]
        result = json.loads(json_result)

        return result

    except Exception as e:
        print(e)
        return {"fullName": "", "email": "", "phone": "", "address": ""}


def parse_vcard(vcard: str):
    try:
        v = vobject.base.readOne(vcard)

        full_name = v.fn.value if hasattr(v, "fn") else None
        email = v.email.value.lower() if hasattr(v, "email") else None
        phone = v.tel.value.replace(" ", "") if hasattr(v, "tel") else None

        address = v.adr.value if hasattr(v, "adr") else None
        if address:
            address_prts = [
                address.street,
                address.city,
                address.region,
                address.code,
                address.country,
            ]
            address = ", ".join(filter(None, address_prts))

        if not (full_name and email and phone and address):
            return None

        return {
            "fullName": full_name,
            "email": email,
            "phone": phone,
            "address": address,
        }

    except:
        return None


def vcard_to_json(s: str):
    parsing_prompt = f"""
        YOUR MISSION:
        You are a data parser. Convert the following vCard text content into a JSON object. The JSON should include only these fields:

        fullName: the contact's full name

        email: the primary email address

        phone: the primary telephone number

        address: the full formatted address as a single string

        Note: Only include the json without anything else!

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
