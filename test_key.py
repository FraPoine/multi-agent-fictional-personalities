import os
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)


# test_key.py is located in the repository root. Its direct parent is therefore
# the project root; parents[1] would incorrectly select the directory above it.
PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

MODEL_NAME = "gpt-5-mini"


def main() -> None:
    # Carica OPENAI_API_KEY dal file .env
    load_dotenv(ENV_PATH)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY non configurata. "
            f"Aggiungi una riga OPENAI_API_KEY=<la_tua_chiave> in {ENV_PATH} "
            "oppure esporta OPENAI_API_KEY nell'ambiente prima di eseguire "
            "lo script."
        )

    print("Chiave trovata nel file .env.")
    print("Invio di una richiesta di test...")

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=MODEL_NAME,
            input="Reply with exactly: API key works",
            max_output_tokens=30,
        )

        print("\nTest riuscito!")
        print(f"Modello: {MODEL_NAME}")
        print(f"Risposta: {response.output_text}")

    except AuthenticationError:
        print("\nErrore: la chiave API non è valida.")

    except RateLimitError:
        print(
            "\nLa chiave è stata riconosciuta, ma hai raggiunto "
            "un limite di utilizzo o non hai credito disponibile."
        )

    except APIConnectionError:
        print(
            "\nErrore di connessione: controlla la connessione Internet."
        )

    except APIStatusError as error:
        print(f"\nErrore API: HTTP {error.status_code}")
        print(error.message)


if __name__ == "__main__":
    main()
