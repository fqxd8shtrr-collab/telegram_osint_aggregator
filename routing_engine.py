import logging
from database import AsyncSessionLocal, SourceChannel, OutputTarget, RoutingRule
from sqlalchemy import select

logger = logging.getLogger(__name__)

class RoutingEngine:
    async def get_targets_for_message(self, source_channel_id, triage_result):
        """
        Returns list of output target IDs where this message should be sent.
        """
        async with AsyncSessionLocal() as session:
            # 1. Get source channel configuration
            source = await session.get(SourceChannel, source_channel_id)
            if not source or not source.enabled:
                return []

            # 2. Get all output targets (enabled)
            targets_result = await session.execute(select(OutputTarget).where(OutputTarget.enabled == True))
            targets = targets_result.scalars().all()

            # 3. Filter based on source's target_outputs if specified
            if source.target_outputs:
                targets = [t for t in targets if t.id in source.target_outputs]

            # 4. Apply video-only filter if source has video_only flag and message lacks video
            if source.video_only:
                # Check if message has video media
                has_video = triage_result.get("has_video", False)
                if not has_video:
                    targets = []

            # 5. Apply custom routing rules (condition matching)
            # Get rules for this source
            rules_result = await session.execute(
                select(RoutingRule).where(RoutingRule.source_channel_id == source_channel_id)
            )
            rules = rules_result.scalars().all()

            final_targets = []
            for target in targets:
                # Check if any rule matches
                match = False
                for rule in rules:
                    if rule.output_target_id == target.id:
                        if self._match_condition(rule.condition, triage_result):
                            match = True
                            break
                # If no rule, use default (send to all)
                if not rules:
                    match = True
                if match:
                    # Also check target's video_only flag
                    if target.video_only:
                        has_video = triage_result.get("has_video", False)
                        if not has_video:
                            continue
                    final_targets.append(target.id)

            return final_targets

    def _match_condition(self, condition, triage_result):
        if not condition:
            return True
        # Example condition: {"event_type": "military", "min_importance": 0.8}
        for key, value in condition.items():
            if key.startswith("min_"):
                field = key[4:]
                if triage_result.get(field, 0) < value:
                    return False
            elif key in triage_result:
                if triage_result[key] != value:
                    return False
        return True

routing_engine = RoutingEngine()
