# succession-ai-backend
The AI backend to The Succession

Requirements:
fastapi
uvicorn
python-dotenv
httpx
pydantic

INSTRUCTIONS:
1. install python, if you have not installed Python on your machine. to check if you have Python installed, copy & paste the following command in your terminal/command prompt:
python --v

3. this command is to create the server. copy & paste this command in your terminal/command prompt:
python -m pip install -r Requiraments.txt

4. this line is to run the server. copy & paste this command line in your terminal/command prompt:
python -m uvicorn Main:app --reload --port 8000

5. to check if the backend is running, put this URL in the browser: http://localhost:8000/health. if a json returned with the status of 'AI scenario backend running', your backend is running.

6. run the frontend : https://github.com/moua0061/CET-Succession 
