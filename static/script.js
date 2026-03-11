// =====================
// Chatbot JS – Multiple Messages + Image + Instruction
// =====================

// =====================
// Chatbot JS – Updated + Streaming AI Explanation
// =====================
// =====================
// Chatbot JS – Streaming AI Response + Explanation + Structure + Folder
// =====================

const userInput = document.getElementById("user-input");
const chatBox = document.getElementById("chat-box");
const sendBtn = document.getElementById("send-btn");
const imageUpload = document.getElementById("image-upload");
const imagePreview = document.getElementById("image-preview");
const previewImg = document.getElementById("preview-img");
const removeImgBtn = document.getElementById("remove-img");
const runBtn = document.getElementById("run-btn");

let selectedImage = null;

// Escape HTML for safe display
function escapeHTML(str) {
  if (!str) return "";
  return str.replace(/[&<>"']/g, (m) => {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[m];
  });
}

// Image preview
imageUpload.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) {
    selectedImage = file;
    previewImg.src = URL.createObjectURL(file);
    imagePreview.style.display = "flex";
  }
});

// Remove image
removeImgBtn.addEventListener("click", () => {
  selectedImage = null;
  imageUpload.value = "";
  previewImg.src = "";
  imagePreview.style.display = "none";
});

// ----------------------
// SEND MESSAGE FUNCTION
// ----------------------
async function sendMessage() {
  const instruction = userInput.value.trim();
  if (!instruction && !selectedImage) return;

  // Show user message
  const userMsg = document.createElement("div");
  userMsg.className = "user-message";

  if (selectedImage) {
    const img = document.createElement("img");
    img.src = URL.createObjectURL(selectedImage);
    img.classList.add("uploaded-img");
    userMsg.appendChild(img);
  }

  if (instruction) {
    const p = document.createElement("p");
    p.textContent = instruction;
    userMsg.appendChild(p);
  }

  chatBox.appendChild(userMsg);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Prepare data
  const formData = new FormData();
  formData.append("instruction", instruction);
  if (selectedImage) formData.append("image", selectedImage);

  // Reset fields
  userInput.value = "";
  imageUpload.value = "";
  selectedImage = null;
  imagePreview.style.display = "none";

  // Show loading message
  const loadingMsg = document.createElement("div");
  loadingMsg.className = "bot-message";
  loadingMsg.textContent = "⚙️ AI is processing your request...";
  chatBox.appendChild(loadingMsg);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const response = await fetch("/stream_process", {
      method: "POST",
      body: formData,
    });

    chatBox.removeChild(loadingMsg);

    if (!response.ok) {
      const errBox = document.createElement("div");
      errBox.className = "bot-message error-message";
      errBox.textContent = `❌ Error: ${response.statusText}`;
      chatBox.appendChild(errBox);
      return;
    }

    // Create explanation streaming container
    const botExpl = document.createElement("div");
    botExpl.className = "bot-message";
    botExpl.innerHTML = `<strong></strong><pre></pre>`;
    chatBox.appendChild(botExpl);
    const preTag = botExpl.querySelector("pre");

    // Streaming response handling
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      let lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.trim()) continue;

        try {
          const data = JSON.parse(line);

          if (data.type === "explanation") {
            preTag.textContent += data.chunk;
          }

          if (data.type === "structure") {
            const structBox = document.createElement("div");
            structBox.className = "bot-message";
            structBox.innerHTML = `<strong></strong><pre>${escapeHTML(data.structure)}</pre>`;
            chatBox.appendChild(structBox);
          }

          // chatBox.scrollTop = chatBox.scrollHeight;

          if (data.type === "folder") {
            const projectFolder = data.project_folder; // store folder name

            const folderBox = document.createElement("div");
            folderBox.className = "bot-message";

            folderBox.innerHTML = `
              <strong></strong> 
              <button 
                onclick="downloadProjectZip('${projectFolder}')"
                style="
                  padding:6px 12px; 
                  background:#4CAF50; 
                  color:white; 
                  border:none; 
                  border-radius:6px; 
                  cursor:pointer; 
                  margin-left:8px;
                ">
                ${projectFolder} ⬇️ Download
              </button>
            `;

            chatBox.appendChild(folderBox);
        }

        chatBox.scrollTop = chatBox.scrollHeight;

        } catch (error) {
          console.warn("Invalid JSON chunk", line);
        }
      }
    }

  } catch (error) {
    console.error(error);
    const errorMsg = document.createElement("div");
    errorMsg.className = "bot-message error";
    errorMsg.textContent = "⚠️ Error processing request. Please try again.";
    chatBox.appendChild(errorMsg);
  }
}

// Send button & Enter key
sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

// =====================
// Download ZIP button
// =====================
async function downloadProjectZip(folderName) {
  try {
    const response = await fetch(`/download_folder?folder=${encodeURIComponent(folderName)}`);

    if (!response.ok) {
      alert("⚠ Folder not found on server!");
      return;
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);

    const tempLink = document.createElement("a");
    tempLink.href = url;
    tempLink.download = folderName + ".zip";
    document.body.appendChild(tempLink);
    tempLink.click();
    tempLink.remove();
    window.URL.revokeObjectURL(url);

  } catch (error) {
    console.error("Download error:", error);
    alert("⚠ Something went wrong while downloading.");
  }
}