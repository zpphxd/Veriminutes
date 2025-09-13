#!/usr/bin/env python3
"""
Test the file upload click functionality programmatically.
"""

import time
import subprocess
import sys

def test_file_input():
    """Test if file input click events are working properly."""

    print("Testing File Upload Click Functionality")
    print("=" * 50)

    # Create a test HTML file that mimics both pages
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>File Input Click Test</title>
    </head>
    <body>
        <h2>Test 1: Upload Page Structure (Currently Broken?)</h2>
        <div id="uploadArea1" style="border: 2px solid red; padding: 20px; cursor: pointer;">
            <p>Click here - Upload Page Style</p>
            <input type="file" id="fileInput1" style="display: none;">
        </div>

        <h2>Test 2: Verify Page Structure (Currently Working)</h2>
        <div id="uploadArea2" style="border: 2px solid green; padding: 20px; cursor: pointer;">
            <p>Click here - Verify Page Style</p>
            <input type="file" id="fileInput2" style="display: none;">
        </div>

        <div id="results" style="margin-top: 20px; padding: 20px; background: #f0f0f0;">
            <h3>Test Results:</h3>
            <pre id="output"></pre>
        </div>

        <script>
            const output = document.getElementById('output');
            let testResults = [];

            // Test 1: Upload page style
            const area1 = document.getElementById('uploadArea1');
            const input1 = document.getElementById('fileInput1');

            area1.addEventListener('click', function(e) {
                if (e.target === input1) return;
                testResults.push('Test 1: Click event fired on upload area');
                input1.click();
                testResults.push('Test 1: Triggered input.click()');
                updateOutput();
            });

            input1.addEventListener('click', function() {
                testResults.push('Test 1: File input received click');
                updateOutput();
            });

            // Test 2: Verify page style
            const area2 = document.getElementById('uploadArea2');
            const input2 = document.getElementById('fileInput2');

            area2.addEventListener('click', function(e) {
                if (e.target === input2) return;
                testResults.push('Test 2: Click event fired on verify area');
                input2.click();
                testResults.push('Test 2: Triggered input.click()');
                updateOutput();
            });

            input2.addEventListener('click', function() {
                testResults.push('Test 2: File input received click');
                updateOutput();
            });

            function updateOutput() {
                output.textContent = testResults.join('\\n');
            }

            // Programmatically test both
            setTimeout(() => {
                testResults.push('\\n=== AUTOMATED TEST ===');
                testResults.push('Simulating click on Test 1 (Upload style)...');
                area1.click();

                setTimeout(() => {
                    testResults.push('\\nSimulating click on Test 2 (Verify style)...');
                    area2.click();

                    // Check if file inputs are accessible
                    setTimeout(() => {
                        testResults.push('\\n=== ACCESSIBILITY CHECK ===');
                        testResults.push('Input 1 parent: ' + (input1.parentElement === area1 ? 'Inside area (GOOD)' : 'Outside area (BAD)'));
                        testResults.push('Input 2 parent: ' + (input2.parentElement === area2 ? 'Inside area (GOOD)' : 'Outside area (BAD)'));
                        updateOutput();
                    }, 100);
                }, 100);
            }, 500);
        </script>
    </body>
    </html>
    """

    # Write test file
    with open('/tmp/test_upload_click.html', 'w') as f:
        f.write(test_html)

    print("Opening test file in browser...")
    subprocess.run(['open', '/tmp/test_upload_click.html'])

    print("\nNow testing the actual VeriMinutes upload page...")
    print("Please manually verify in your browser at http://localhost:8787")
    print("\nExpected behavior:")
    print("1. Click on 'Drop your .txt transcript here' area")
    print("2. Finder/file dialog should open")
    print("3. You should be able to select a .txt file")

    # Also create a quick curl test to verify server is running
    print("\nChecking if server is running...")
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:8787'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.stdout == '200':
            print("✅ Server is running at http://localhost:8787")
        else:
            print(f"⚠️ Server returned status code: {result.stdout}")
    except:
        print("❌ Could not connect to server at http://localhost:8787")

if __name__ == "__main__":
    test_file_input()