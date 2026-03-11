from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Header
from pydantic import BaseModel
from PIL import Image
import io
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoProcessor, AutoModelForVision2Seq, BitsAndBytesConfig
from transformers import MllamaForConditionalGeneration, AutoProcessor
from huggingface_hub import login
import torch
#=-=-=-=-=-=-=     library -=-=-=-=-=-=-=-=-=     
local_path = "/home/ubuntu/collm/code_generate"
SECRET_KEY = "Arjun_123"


#=-=-=-=-=-=-= Quantisation -=-=-=-=-=-=-=-=-=  

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True
)

#=-=-=-=-=-=-=-=- Processor -=-=-=-=-=-=-=-=-=
processor = AutoProcessor.from_pretrained(local_path)
model = AutoModelForVision2Seq.from_pretrained(
    local_path,
    quantization_config=bnb_config,
    device_map="auto",
)

print("========== model_loaded_succesfully -=-=-=-=-=-=-=-=-=-=-=-")

app = FastAPI(title="Meta_llama model Custom API")

class Query(BaseModel):
    prompt: str

@app.get("/")
async def home():
    return {"message": "Meta lama API is running successfully 🎉"}



@app.post("/generate")
async def generate_text(
    prompt: str = Form(...),
    image: UploadFile = File(None),
    secret_key: str = Header(None) 
):
    if secret_key and secret_key != SECRET_KEY:
        raise HTTPException(status_code=401, detail="❌ Invalid Secret Key")

    try:
        # ======== Text Only ========
        if image is None:
            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ]
            print("-=-=-=-== messages -=-=-=-==",messages)

            input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
            print("-=-=-=-===-=-=-== input_text -=-=--==-=-=-=-=",input_text)
            inputs = processor(text=input_text, return_tensors="pt").to(model.device)
            print("-=-=-=-===-=-=-== inputs -=-=--==-=-=-=-=",inputs)

            output = model.generate(
                **inputs,
                max_new_tokens=3000,
                temperature=0.2,
                top_p=0.9,
            )

            response = processor.decode(output[0])
            print("-=-=-=-===-=-=-== response -=-=--==-=-=-=-=",response)
            return {"response": response}

        # ======== Image + Text ========
        else:
            img_bytes = await image.read()
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            messages = [
                {"role": "user", "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt}
                ]}
            ]
            print("-=-=-=-== img_messages -=-=-=-==",messages)

            input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
            print("-=-=-=-===-=-=-== input_text -=-=--==-=-=-=-=",input_text)

            inputs = processor(
                images=img,
                text=input_text,
                add_special_tokens=False,
                return_tensors="pt"
            ).to(model.device)
            print("-=-=-=-===-=-=-== inputs -=-=--==-=-=-=-=",inputs)

            output = model.generate(
                **inputs,
                max_new_tokens=1500,
                temperature=0.3,
                top_p=0.95,
            )

            response = processor.decode(output[0])
            print("-=-=-=-===-=-=-== response -=-=--==-=-=-=-=",response)
            return {"response": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



#  uvicorn app:app --host 0.0.0.0 --port 8000 --reload


# http://100.30.183.119:8000
# uvicorn -w 1 --threads 8 -b 0.0.0.0:8000 app:app --timeout 900



# Run with:
# uvicorn app:app --host 0.0.0.0 --port 5000 --reload



#  uvicorn app:app --host 0.0.0.0 --port 8000 --reload


# http://3.80.244.41:5000
# uvicorn -w 1 --threads 8 -b 0.0.0.0:8000 app:app --timeout 900
