# Prompt: Extract Persona

You are given text examples associated with a fictional character.

Your task is to extract a structured persona profile that can be used to condition an LLM agent.

Return valid JSON only.

## Character

Name: {character_name}

Description:
{character_description}

## Corpus examples

{corpus_examples}

## Output schema

Return this JSON structure:

```json
{
  "style": {
    "tone": "",
    "sentence_length": "",
    "formality": "",
    "emotion_level": ""
  },
  "values": [],
  "motivations": [],
  "speech_patterns": [],
  "interaction_rules": [],
  "example_utterances": [],
  "limitations": []
}
```

## Requirements

- Do not claim the character is real.
- Do not include unsupported traits.
- Distinguish between speech style and behavioral motivation.
- Avoid stereotypes unless they are directly supported by the corpus.
- Keep the profile concise and usable for generation.
