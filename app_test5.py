from flask import Flask, render_template, request, jsonify
from flask import send_from_directory
import os
from typing import Optional
import pathlib
import uuid

from huggingface_hub import login
import datetime
import re
from textwrap import dedent

# import cv2
import json
import requests
# import torch
from PIL import Image
import tiktoken
import zipfile
# import os
import time

from flask import send_file, abort
import requests
from flask import Response


API_URL = "http://3.84.146.210:8000/generate"  
API_KEY = "Arjun_123"

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
MEMORY_FILE = "memory.json"

encoding = tiktoken.get_encoding("cl100k_base")
def count_tokens(text: str) -> int:
    return len(encoding.encode(text))
def load_memory():
    """Load existing memory or create a new one if file doesn't exist."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            try:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
                return data
            except json.JSONDecodeError:
                return {}
    return {}  

def save_memory(memory):
    """Save memory dictionary to file."""
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

# ----------------------------
# Example usage
# ----------------------------
memory = load_memory()

print("========== sucessfully previous question -=-=-=-=-=-=-=-=-=-=-=-")


#===============================================================

def extract_explanation(text):
    """
    Extracts the explanation block from text.
    Works for:
      - **EXPLANATION**
      - # EXPLANATION
      - # EXPLANATION (without trailing **)
    Stops at:
      - Next **EXPLANATION** or # EXPLANATION
      - <|eot_id|>
    """
    pattern = r"(?:\*\*|#)\s*EXPLANATION\s*(?:\*\*)?\s*(.*?)(?=(?:\*\*|#)\s*EXPLANATION|<\|eot_id\|>|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""



#============================================================
#=Remove Explanation Block

def remove_explanation_block(text):
    pattern = r"\*\*EXPLANATION\*\*\s*(.*?)(?:<\|eot_id\|>|$)"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()


#=======================================================================
#Extract Project Structure 

def extract_project_structure(text):
    pattern = r"(Project:\s*.*?)(?=# Project Dependencies)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""

#=======================================================================
#Remove Header Block

def remove_header_block(text):
    pattern = r"<\|begin_of_text\|>.*?<\|start_header_id\|>assistant<\|end_header_id\|>"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()

#=======================================================================





def extract_project_name(text):
    m = re.search(r"#\s*Project:\s*(.+)", text)
    if m:
        return m.group(1).strip().replace(" ", "_").lower()

    m = re.search(r"#\s*([\w\-]+)/\s*$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()

    return "output_project"




def extract_and_save_files(text):
    text = text.strip()
    project_structure_patterns = [
        r"\*\*Project Structure:\*\*", 
        r"#\s*Project Structure:"       
    ]

    is_project = any(re.search(pattern, text, re.IGNORECASE) for pattern in project_structure_patterns)

    if is_project:
        print("✅ Project format detected!")
        return extract_and_files(text)
    else:
        print("⚠ Simple code-only output detected!")
        return extract_single_code_file(text)



def extract_and_files(text):
    base_folder = extract_project_name(text)
    os.makedirs(base_folder, exist_ok=True)

    print(f"📁 Project folder detected: {base_folder}")

    file_pattern = re.compile(r"^#\s*(.+?\.\w+)\s*$", re.MULTILINE)
    matches = list(file_pattern.finditer(text))
    saved_files = []

    for i, match in enumerate(matches):
        file_path = match.group(1).strip()
        if file_path.startswith("|-") or file_path.startswith("-"):
            continue

        file_path = file_path.replace("|-", "").replace("-", "").strip()

        start_index = match.end()
        end_index = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start_index:end_index].strip("\n")
        content = re.sub(r"```[a-zA-Z0-9]*", "", content).replace("```", "").strip()
        full_path = os.path.join(base_folder, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✔ Saved → {full_path}")
        saved_files.append(full_path)

    print("\n✅ All clean files extracted!")
    return base_folder



EXT_MAP = {
    "python": "py",
    "py": "py",
    "javascript": "js",
    "js": "js",
    "typescript": "ts",
    "ts": "ts",
    "html": "html",
    "htm": "html",
    "css": "css",
    "json": "json",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "bash": "sh",
    "shell": "sh",
    "text": "txt",
    "txt": "txt",
}


    
def extract_single_code_file(text):
    text = text.strip()
    combined_pattern = r"\*{0,2}#\s*(?P<filename>[A-Za-z0-9_\-./]+)\*{0,2}\s*```(?:[a-zA-Z0-9]+)?\s+(?P<code>[\s\S]*?)```"
    m = re.search(combined_pattern, text, re.MULTILINE)

    if m:
        filename = m.group("filename")
        code = m.group("code").strip()
    else:
        fence_pattern = r"```([a-zA-Z0-9]+)?\s+([\s\S]*?)```"
        m1 = re.search(fence_pattern, text)
        if m1:
            lang = m1.group(1) or "py"
            code = m1.group(2).strip()
            ext = EXT_MAP.get(lang.lower(), "txt")
            filename = f"file.{ext}"

        else:
            simple_hash_pattern = r"#\s*(?P<filename>[A-Za-z0-9_\-./]+)\s*\n+(?P<code>[\s\S]*)"
            m2 = re.search(simple_hash_pattern, text)

            if m2:
                filename = m2.group("filename")
                code = m2.group("code").strip()
            else:
                print("❌ ERROR: No valid code found")
                return None

    code = re.sub(r"<\|.*?\|>", "", code).strip()

    base, ext = os.path.splitext(filename)

    counter = 0
    while True:
        folder_name = f"{base}" if counter == 0 else f"{base}_{counter}"
        if not os.path.exists(folder_name):
            break
        counter += 1

    os.makedirs(folder_name, exist_ok=True)
    file_path = os.path.join(folder_name, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"✔ Saved: {file_path}")
    return folder_name




#====================-=-=-=-=. api create -=-=-=-=-=-=-=-=-=-=====================



@app.route('/')
def index():
    return render_template('index.html')


@app.route("/stream_process", methods=["POST"])
def process():
    try:
        image_file = request.files.get("image", None)
        user_input = request.form.get("instruction", "").strip()
        print("=-=-=-=-=-=-=-=-=- user_input -=-=-=-=-=-=-=-=",user_input)
        

        if image_file and image_file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
            print("-=-=-= A-=-=-=-=-")
            original_filename = os.path.basename(image_file.filename)
            safe_filename = re.sub(r"[^A-Za-z0-9_.-]", "_", original_filename)
            filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_filename}"
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(image_path)
            image = Image.open(image_path)
            payload = {"prompt": f"""You are an **advanced AI code generator** capable of understanding **any image** and converting it into **runnable code** based on user instructions.
                        ### 🎯 Primary Objective:
                        The user will upload an **image** (it may be a flowchart, diagram, screenshot, UI mockup, code image, or any visual content).  
                        Your task is to:
                        1. **Analyze and understand** the image content and visual structure.
                        2. **Extract text and context** from the image (using OCR and visual reasoning).
                        3. **Interpret the meaning** and relate it to the user's provided **instructions**.
                        4. **Generate runnable code** according to the **user-specified language** and **Rules for Code Generation**.
                        5. **After the code generate explain the code in text form below give example. 
                            **EXPLANATION**
                            <explanation here>

                        ---

                        ### ⚙️ Rules for Code Generation:
                            1. Understand **visual structure**, **arrows**, **text**, and **object relationships** in the image.
                            2. If the image represents a **flowchart**, follow these shape rules:
                                - **Rectangle** → Input/Output operation  
                                - **Diamond** → Conditional logic (`if`, `else`, `while`, etc.)  
                                - **Parallelogram** → Processing/Computation (e.g., variable assignment, print)  
                                - **Ellipse (oval)** → Start/End or Function declaration  
                            3. If the image represents **other contexts** (UI, code snippet, architecture, design, etc.), 
                                - Interpret what the user likely wants to **build, simulate, or generate** from it.
                            4. Always follow the **user’s instruction** about what to generate (e.g., “generate Python code”, “convert to JavaScript function”, “build UI layout in React”).
                            5. Code must be **syntactically correct**, **well-indented**, and **directly executable**.
                            6. **No explanation, no description — only output runnable code**.
                            7. The output must match **user-specified language** exactly.
                        
                            

                        ---

                        ### 🧩 Output Format:
                        - Output **only runnable code** No extra text, no markdown, no comments in code.
                        - After the code genrate explain code in text from
                            **EXPLANATION**
                            <explanation here>
                          

                        **User Instruction / Language:** {user_input}
                        """}

            files = {"image": open(image_path, "rb")}  
            headers = {"x-api-key": API_KEY}  

            response = requests.post(API_URL, headers=headers, files=files, data=payload)

            if response.status_code == 200:
                final_text = response.json().get("response", "")
                print(final_text)
            else:
                print("Error:", response.status_code, response.text)

            
            print("-=--=-==-=-=-=-= final_text -=-=-=--=-=-=-==",final_text)

            text = remove_header_block(final_text)
            print("-=-=---=-=--=-=-=- text -=-=-=-=-=-=-=-=-=-=-=-=",text)
            tf = remove_explanation_block(text)

            sf = extract_and_save_files(tf)
            print("-=-=---=-=--=-=-=- sf -=-=-=-=-=-=-=-=-=-=-=-=",sf)

            memory["new_text"] = final_text
            save_memory(memory)
            explanation = extract_explanation(text)
            print("-=-=-=-=- explanation -=-=-=-=-=--=-=",explanation)
            def generate_stream():
                if explanation and explanation.strip():
                    for ch in explanation:
                        yield json.dumps({"type": "explanation", "chunk": ch}) + "\n"
                        time.sleep(0.05)  
                if sf:
                    yield json.dumps({"type": "folder", "project_folder": sf}) + "\n"
                    time.sleep(0.05)

            return Response(generate_stream(), mimetype="application/json")

        else:
            payload = {"prompt": f"""
            You are an AI Coding Assistant. Your role is to understand user instructions and generate complete, runnable code.

            Follow these rules:
            1. if user ask with greeting example:- Hi,Hello etc then response with greeting.
            1. Read and understand the user’s instruction carefully.
            2. Generate clean, executable code in the user-specified programming language and add the file name on the top of the code exaple like:- "#file1.ext","#file1.py" etc.
            3. If the language is not specified, default to Python.
            4. The code should be logically correct, properly indented, and ready to run without modification.
            5. Do not add explanations, comments, or extra text unless requested.
            6. After the code generate explain the code in text form.
            7. If user query contains 'create project', generate complete project folder structures with files and full code. **ALWAYS output the project in this exact format.
               example:-
               ```
                    # Project: <PROJECT NAME>

                    # Project Structure:
                    # <folder>/
                    #   |- file1
                    #   |- file2
                    #   |- folder2/
                    #       |- fileA
                    #       |- fileB

                    # Project Dependencies:
                    #   - dependency1
                    #   - dependency2

                    # Project Code:

                    # file1.ext
                    <full code here>

                    # folder2/fileA.ext
                    <full code here>

                    # folder2/fileB.ext
                    <full code here>

                    # requirements.txt
                    <dependencies listed>
            **EXPLANATION**
            <explanation here>
            
            user_input: {user_input}
            
            **Generated Code:**
            """}
            headers = {"x-api-key": API_KEY}

            response = requests.post(API_URL, data=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                final_text = data.get("response", "")
            else:
                return jsonify({"status": "error", "message": response.text}), 400

            print("-=--=-==-=-=-=-= final_text -=-=-=--=-=-=-==",final_text)

            text = remove_header_block(final_text)
            print("-=-=---=-=--=-=-=- text -=-=-=-=-=-=-=-=-=-=-=-=",text)
            tf = remove_explanation_block(text)
            print("-=-=---=-=--=-=-=- text -=-=-=-=-=-=-=-=-=-=-=-=",tf)

            sf = extract_and_save_files(tf)
            print("-=-=---=-=--=-=-=- sf -=-=-=-=-=-=-=-=-=-=-=-=",sf)
            clean_text = extract_project_structure(text)
            print("-=-=-clean_text-=-=-=-=-=",clean_text)

            memory["new_text"] = final_text
            save_memory(memory)
            explanation = extract_explanation(text)
            print("-=-=-=-=- explanation -=-=-=-=-=--=-=",explanation)            
            def generate_stream():                
                if explanation and explanation.strip():
                    for ch in explanation:
                        yield json.dumps({"type": "explanation", "chunk": ch}) + "\n"
                        time.sleep(0.05)  
                if clean_text and clean_text.strip():
                    yield json.dumps({"type": "structure", "structure": clean_text}) + "\n"
                    time.sleep(0.05)
                if sf:
                    yield json.dumps({"type": "folder", "project_folder": sf}) + "\n"
                    time.sleep(0.05)

            return Response(generate_stream(), mimetype="application/json")
    except Exception as e:
        return Response(json.dumps({"error": f"Error processing request: {str(e)}"}), mimetype="application/json")

def make_zip(folder_path):
    folder_path = os.path.abspath(folder_path)
    zip_path = folder_path + ".zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
    return zip_path

@app.route("/download_folder")
def download_folder():
    folder = request.args.get("folder")
    if not folder:
        return "Folder missing", 400

    folder_path = os.path.abspath(folder)
    print(folder_path,"===-=-=-=-=-=-=-= folder_path -=-=-=-=--=-")
    if not os.path.exists(folder_path):
        return "Folder not found", 404

    zip_file = make_zip(folder_path)
    print(zip_file,"-=-=-=-=-=-=-=-=-=--=-=---=-=-=-=-=-=-")
    return send_file(zip_file, as_attachment=True)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)




# gunicorn -w 1 -b 0.0.0.0:8501 app_test5:app --timeout 300
# http://54.196.73.25:8501 
# gunicorn -w 1 --threads 8 -b 0.0.0.0:8000 app_test5:app --timeout 900




# gunicorn -w 1 -b 0.0.0.0:8000 app:app --timeout 900