import os
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8000"))

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing from .env")


app = FastAPI(title="The Succession AI Scenario Engine")


# ---------- Request Model ----------

class ScenarioRequest(BaseModel):
    week: int = Field(..., ge=1)
    phase: int = Field(..., ge=1)
    power: int = Field(..., ge=0)
    loyalty: int = Field(..., ge=0)
    heat: int = Field(..., ge=0)
    onBlacklistedState: bool


# ---------- Response Model ----------

class EffectModel(BaseModel):
    power: int
    loyalty: int
    heat: int


class ChoiceModel(BaseModel):
    label: Literal["ALLY", "LEVERAGE", "COVER"]
    text: str
    effects: EffectModel
    outcome: str


class ScenarioResponse(BaseModel):
    title: str
    brief: str
    choices: List[ChoiceModel]
    hint: str
    tone: Literal["supportive", "neutral", "suspicious", "paranoid", "threatening"]


# ---------- Helpers ----------

def clamp_effect(value: int) -> int:
    # Keeps AI-generated stat changes balanced
    return max(-3, min(3, value))


def sanitize_response(data: dict) -> dict:
    # Make sure exactly 3 choices exist
    if "choices" not in data or len(data["choices"]) != 3:
        raise ValueError("AI did not return exactly 3 choices.")

    # Clamp all effects
    for choice in data["choices"]:
        choice["effects"]["power"] = clamp_effect(choice["effects"]["power"])
        choice["effects"]["loyalty"] = clamp_effect(choice["effects"]["loyalty"])
        choice["effects"]["heat"] = clamp_effect(choice["effects"]["heat"])

    return data


# ---------- Routes ----------

@app.get("/health")
async def health():
    return {"status": "AI scenario backend running"}


@app.post("/generateScenario", response_model=ScenarioResponse)
async def generate_scenario(payload: ScenarioRequest):
    system_prompt = (
        "You are generating weekly political strategy content for an Android game called "
        "'The Succession'. The game is a political thriller where the player must balance "
        "Power, Loyalty, and Heat. Return only valid JSON matching the schema."
    )

    user_prompt = f"""
Current game state:
- week: {payload.week}
- phase: {payload.phase}
- power: {payload.power}
- loyalty: {payload.loyalty}
- heat: {payload.heat}
- onBlacklistedState: {payload.onBlacklistedState}

Requirements:
- Generate exactly 1 political scenario title
- Generate exactly 1 short scenario brief
- Generate exactly 3 choices labeled ALLY, LEVERAGE, and COVER
- Each choice must include:
  - label
  - text
  - effects with power, loyalty, and heat
  - outcome
- Keep all effects small and balanced
- Each effect should be between -3 and +3
- If onBlacklistedState is true, make the scenario focus on public pressure, scandal recovery, or political redemption
- If power and loyalty are high while heat is low, make the scenario feel close to securing the presidency
- Keep the tone political, strategic, and serious
- Add a short gameplay hint
- Return one tone value

Return JSON only.
"""

    request_body = {
        "model": "gpt-4.1-mini",
        "instructions": system_prompt,
        "input": user_prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "succession_scenario",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "brief": {"type": "string"},
                        "choices": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "enum": ["ALLY", "LEVERAGE", "COVER"]
                                    },
                                    "text": {"type": "string"},
                                    "effects": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "power": {"type": "integer"},
                                            "loyalty": {"type": "integer"},
                                            "heat": {"type": "integer"}
                                        },
                                        "required": ["power", "loyalty", "heat"]
                                    },
                                    "outcome": {"type": "string"}
                                },
                                "required": ["label", "text", "effects", "outcome"]
                            }
                        },
                        "hint": {"type": "string"},
                        "tone": {
                            "type": "string",
                            "enum": ["supportive", "neutral", "suspicious", "paranoid", "threatening"]
                        }
                    },
                    "required": ["title", "brief", "choices", "hint", "tone"]
                }
            }
        },
        "max_output_tokens": 600
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers=headers,
                json=request_body
            )

        response.raise_for_status()
        raw = response.json()

        content_items = raw["output"][0]["content"]

        parsed_json = None
        for item in content_items:
            if item.get("type") == "output_text":
                text_value = item.get("text", "")
                parsed_json = json.loads(text_value)
                break

        if parsed_json is None:
            raise ValueError("Could not parse structured scenario output from model.")

        cleaned = sanitize_response(parsed_json)
        return ScenarioResponse(**cleaned)

    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="OpenAI request timed out")

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
