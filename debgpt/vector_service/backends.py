"""Backend adapters for the vector-service generation endpoint."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


def generate_with_ollama(prompt: str, options: Dict[str, Any]) -> str:
    model = options.get("model", "llama2")
    url = f"{OLLAMA_URL}/api/generate"
    payload = {"model": model, "prompt": prompt,
               "options": options.get("options", {})}
    response = requests.post(
        url, json=payload, timeout=options.get("timeout", 120))
    response.raise_for_status()
    data = response.json()
    return data.get("output") or data.get("result") or json.dumps(data)


try:  # Optional dependency (vector-service extra)
    from llama_cpp import Llama  # type: ignore

    _LLAMA_CPP_AVAILABLE = True
except Exception:  # pragma: no cover - handled at runtime
    _LLAMA_CPP_AVAILABLE = False


def generate_with_llamacpp(prompt: str, options: Dict[str, Any]) -> str:
    if not _LLAMA_CPP_AVAILABLE:
        raise RuntimeError(
            "llama-cpp-python is not installed. Install the 'vector-service' extra.")
    model_path = options.get("model_path")
    if not model_path:
        raise ValueError("'model_path' is required for the llamacpp backend")
    llm = Llama(model_path=model_path)
    result = llm.create(
        prompt=prompt,
        max_tokens=options.get("max_tokens", 256),
        temperature=options.get("temperature", 0.2),
    )
    return result.get("choices", [{}])[0].get("text", "")


try:  # Optional dependency (vector-service extra)
    import openai

    _OPENAI_AVAILABLE = True
except Exception:  # pragma: no cover - handled at runtime
    _OPENAI_AVAILABLE = False


def generate_with_openai(prompt: str, options: Dict[str, Any]) -> str:
    if not _OPENAI_AVAILABLE:
        raise RuntimeError(
            "openai package is not installed. Install the 'vector-service' extra.")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is required for the OpenAI backend")
    openai.api_key = api_key
    model = options.get("model", "gpt-4o-mini")
    response = openai.Completion.create(
        model=model,
        prompt=prompt,
        max_tokens=options.get("max_tokens", 256),
    )
    return response.choices[0].text


try:  # Optional dependency (vector-service extra)
    from google.cloud import aiplatform  # type: ignore

    _GOOGLE_AVAILABLE = True
except Exception:  # pragma: no cover - handled at runtime
    _GOOGLE_AVAILABLE = False


def generate_with_google(prompt: str, options: Dict[str, Any]) -> str:
    if not _GOOGLE_AVAILABLE:
        raise RuntimeError(
            "google-cloud-aiplatform package is not installed. Install the 'vector-service' extra."
        )
    project = options.get("project") or os.getenv("GCP_PROJECT")
    location = options.get("location") or os.getenv(
        "GCP_LOCATION", "us-central1")
    model_name = options.get("model_name")
    if not project or not model_name:
        raise RuntimeError(
            "'project' and 'model_name' are required for the Google backend")
    aiplatform.init(project=project, location=location)
    model = aiplatform.Model(model_name)
    prediction = model.predict(
        instances=[prompt], parameters=options.get("parameters", {}))
    return prediction.predictions[0]


def generate_with_huggingface(prompt: str, options: Dict[str, Any]) -> str:
    token = os.getenv("HUGGINGFACE_API_TOKEN")
    if not token:
        raise RuntimeError(
            "HUGGINGFACE_API_TOKEN environment variable is required for the Hugging Face backend")
    model = options.get("model", "meta-llama/Llama-2-7b")
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": prompt, "parameters": options.get("parameters", {})}
    response = requests.post(url, headers=headers,
                             json=payload, timeout=options.get("timeout", 120))
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        return data[0].get("generated_text", str(data))
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(data["error"])
    return str(data)


_BACKENDS = {
    "ollama": generate_with_ollama,
    "llamacpp": generate_with_llamacpp,
    "llama.cpp": generate_with_llamacpp,
    "llama_cpp": generate_with_llamacpp,
    "openai": generate_with_openai,
    "google": generate_with_google,
    "vertex": generate_with_google,
    "hf": generate_with_huggingface,
    "huggingface": generate_with_huggingface,
}


def generate_with_backend(name: str, prompt: str, options: Dict[str, Any]) -> str:
    name = name.lower()
    if name not in _BACKENDS:
        raise ValueError(f"Unknown backend: {name}")
    return _BACKENDS[name](prompt, options or {})
