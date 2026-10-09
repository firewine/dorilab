UPDATE model_runs
SET token_usage = jsonb_set(
    token_usage,
    '{reserved_new_tokens}',
    COALESCE(
        receipt->'reserved_output_tokens',
        receipt->'max_new_tokens',
        receipt->'response_reservation'
    ),
    true
)
WHERE COALESCE(
        receipt->'reserved_output_tokens',
        receipt->'max_new_tokens',
        receipt->'response_reservation'
    ) IS NOT NULL
  AND (
      NOT token_usage ? 'reserved_new_tokens'
      OR token_usage->'reserved_new_tokens' = 'null'::jsonb
  );
