document.addEventListener("DOMContentLoaded",()=>{
  console.log("My Gizmo ready 💫");
});
document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("fileInput");
  const fileName = document.getElementById("file-name");
  const watermarkInput = document.getElementById("watermarkInput");
  const watermarkName = document.getElementById("watermark-name");

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      fileName.textContent = fileInput.files.length
        ? `${fileInput.files.length} file(s) selected`
        : "No file chosen";
    });
  }

  if (watermarkInput) {
    watermarkInput.addEventListener("change", () => {
      watermarkName.textContent = watermarkInput.files.length
        ? watermarkInput.files[0].name
        : "No file chosen";
    });
  }
});
