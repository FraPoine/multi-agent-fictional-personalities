"""Legacy round-discussion adapter for the original Sprint 7 compatibility UI."""

from dataclasses import dataclass
from datetime import datetime

from multi_agent_personalities.application.investigation_tasks import (
    investigation_discussion_task_name,
)
from multi_agent_personalities.application.investigation_prompts import (
    InvestigationPromptTemplate,
    render_discussion_messages,
    render_investigation_prompt,
    render_persona_context,
)
from multi_agent_personalities.models import Message
from multi_agent_personalities.simulation.participant import (
    ConversationParticipant,
)


@dataclass(frozen=True)
class InvestigationDiscussionReplyGenerator:
    """Render and generate one selected turn from fixed round context."""

    template: InvestigationPromptTemplate
    session_id: str
    round_id: str
    round_index: int
    case_introduction: str
    visible_clues: str
    analyses: str
    completed_history: str

    def __call__(
        self,
        *,
        participant: ConversationParticipant,
        history: tuple[Message, ...],
        topic: str,
        run_id: str,
        turn_index: int,
        timestamp: datetime,
    ) -> Message:
        """Generate one normal message without choosing the speaker or turn."""
        del topic
        prompt = render_investigation_prompt(
            self.template,
            {
                "session_id": self.session_id,
                "round_id": self.round_id,
                "case_introduction": self.case_introduction,
                "participant_id": participant.character_id,
                "persona_profile": render_persona_context(participant.persona),
                "visible_clues": self.visible_clues,
                "analyses": self.analyses,
                "completed_history": self.completed_history,
                "discussion_history": render_discussion_messages(history),
            },
        )
        generation = participant.provider.generate(
            prompt,
            task_name=investigation_discussion_task_name(
                participant.character_id,
                self.round_index,
                turn_index,
            ),
        )
        if generation.metadata.provider != participant.provider_name:
            raise ValueError(
                "declared provider does not match generation metadata provider"
            )
        reported_model = generation.metadata.model
        if (
            reported_model is not None
            and participant.model_name is not None
            and reported_model != participant.model_name
        ):
            raise ValueError(
                "declared model does not match generation metadata model"
            )
        effective_model = (
            reported_model
            if reported_model is not None
            else participant.model_name
        )
        return Message(
            message_id=f"{run_id}_msg_{turn_index + 1:04d}",
            run_id=run_id,
            turn_index=turn_index,
            speaker_character_id=participant.character_id,
            speaker_name=participant.display_name,
            text=generation.text,
            provider=generation.metadata.provider,
            model=effective_model,
            generation_metadata=generation.metadata,
            timestamp=timestamp,
        )
