import os
import json
import numpy as np

from typing import TypedDict
from PIL import Image
from io import BytesIO
from fastapi import FastAPI, UploadFile
from qreader import QReader

from mistralai import Mistral
from typing import Optional 


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

@app.get("/search-web")
async def search_web(
    full_name: str,
    email: str,
    company: str,
    website: Optional[str] = None,
    phone_number: Optional[str] = None,
    address: Optional[str] = None,
):
    # Step 1: Build the search prompt
    query_prompt = f"""
            You are an advanced research assistant with access to live web data. Your goal is to find verified and relevant public information about a person and their company.

            ### INPUT DATA:
            - Full Name: {full_name}
            - Email: {email}
            - Company: {company}
            {"- Website: " + website if website else ""}
            {"- Phone Number: " + phone_number if phone_number else ""}
            {"- Address: " + address if address else ""}

            ### TASK:
            Use all available web search tools to gather the following:

            1. **Public Social Media Profiles** (X/Twitter, LinkedIn, Facebook)
            2. **Recent Business-Related Posts** from X and LinkedIn that mention the person or their company
            3. **A Publicly Available Photo URL** of the person
            4. **Mentions of the company in news, blogs, or online media**
            5. If any information is unavailable, explain why and suggest possible next steps.

            Only include data from reliable and publicly accessible sources.
        """

    
    websearch_agent = mistral_client.beta.agents.create(
        model="mistral-medium-2505",
        description="Agent able to search information over the web, such as social media, news, and company profiles.",
        name="Websearch Agent",
        instructions="You can use web_search to find current and relevant public information across social platforms, company websites, and news sources.",
        tools=[{"type": "web_search"}],
        completion_args={
            "temperature": 0.3,
            "top_p": 0.95,
        }
    )

    
    result = websearch_agent.run(query_prompt)

    return {
        "result": result.output  
    }
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
