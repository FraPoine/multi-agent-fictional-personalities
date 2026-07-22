# Prompt: Extract Persona

Version: `v1`

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
  "character_id": "",
  "display_name": "",
  "description": "",
  "speaking_style": [],
  "reasoning_style": [],
  "personality_traits": [],
  "behavior_rules": [],
  "example_messages": []
}
```

## Requirements

- Do not claim the character is real.
- Do not include unsupported traits.
- Distinguish between speaking style, reasoning style, and personality traits.
- Avoid stereotypes unless they are directly supported by the corpus.
- Keep the profile concise and usable for generation.
- Use a lowercase `snake_case` identifier for `character_id`.
- Set `display_name` to the character name given above.
- Write a short, corpus-grounded summary in `description`.
- Put only short strings in the array fields; do not return nested objects.
- Use `speaking_style` for how the character speaks and `reasoning_style` for how the character thinks.
- Use `personality_traits` for stable traits and `behavior_rules` for instructions the agent should follow.
- Include only representative, corpus-supported lines in `example_messages`.
- Return exactly these fields and no others.
