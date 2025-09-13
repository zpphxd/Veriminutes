// Paste this into the browser console on http://localhost:8787

console.clear();
console.log("=== CHECKING UPLOAD PAGE STRUCTURE ===");

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');

console.log("1. Upload area exists:", uploadArea ? "✓" : "✗");
console.log("2. File input exists:", fileInput ? "✓" : "✗");

if (uploadArea && fileInput) {
    console.log("3. File input parent:", fileInput.parentElement);
    console.log("4. Is file input inside upload area?",
        uploadArea.contains(fileInput) ? "✓ YES" : "✗ NO");

    console.log("5. File input style:");
    console.log("   - display:", window.getComputedStyle(fileInput).display);
    console.log("   - visibility:", window.getComputedStyle(fileInput).visibility);
    console.log("   - position:", window.getComputedStyle(fileInput).position);

    console.log("\n6. Testing click programmatically...");

    // Add temporary listener to see if click reaches file input
    const tempHandler = (e) => {
        console.log("   ✓ File input received click event!");
        fileInput.removeEventListener('click', tempHandler);
    };
    fileInput.addEventListener('click', tempHandler);

    // Trigger click
    setTimeout(() => {
        console.log("   Triggering fileInput.click()...");
        fileInput.click();
    }, 100);

    console.log("\n7. Click handlers on uploadArea:");
    // Check if there are event listeners
    const listeners = getEventListeners ? getEventListeners(uploadArea) : null;
    if (listeners) {
        console.log("   Click listeners:", listeners.click ? listeners.click.length : 0);
    }

    console.log("\n=== DIAGNOSIS ===");
    if (!uploadArea.contains(fileInput)) {
        console.error("❌ PROBLEM: File input is NOT inside upload area!");
        console.log("This will prevent clicks from working properly.");
        console.log("FIX: Move <input> inside the <div id='uploadArea'>");
    } else {
        console.log("✓ Structure looks correct");
        console.log("If clicking still doesn't work, check for JavaScript errors");
    }
} else {
    console.error("❌ Critical elements missing!");
}

console.log("\n=== TEST COMPLETE ===");
console.log("Now try clicking the upload area manually.");