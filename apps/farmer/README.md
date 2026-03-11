# farmer (v2)

`farmer` is a CLI-first lifecycle orchestration tool for WRG product/idea incubation.
It manages ideas from seed intake to scoring, growth, care, harvest, storage, and portfolio decision.

## Lifecycle States

- `seed`
- `scored`
- `queued`
- `sprout`
- `growing`
- `maturing`
- `harvestable`
- `harvested`
- `stored`
- `hold`
- `retired`
- `composted`

Valid transition intent (golden path):

- `seed -> scored -> queued -> sprout -> growing -> maturing -> harvestable -> harvested -> stored`
- Exception paths: `hold`, `retired`, `composted`

## Core Commands

```bash
python -m farmer.cli seed add --name idea_x --title "Idea X" --category automation --problem "manual work" --target-user "ops" --internal-value 8 --external-value 6 --complexity 3
python -m farmer.cli seed list
python -m farmer.cli seed show idea_x
python -m farmer.cli seed show idea_x --json
python -m farmer.cli show idea_x
python -m farmer.cli show idea_x --json
python -m farmer.cli seed score idea_x
python -m farmer.cli seed queue idea_x
python -m farmer.cli grow start idea_x
python -m farmer.cli grow run
python -m farmer.cli grow show idea_x
python -m farmer.cli care run
python -m farmer.cli care show idea_x
python -m farmer.cli harvest check idea_x
python -m farmer.cli harvest run
python -m farmer.cli harvest list
python -m farmer.cli warehouse list
python -m farmer.cli warehouse move idea_x --to external_candidates
python -m farmer.cli select idea_x
python -m farmer.cli events
python -m farmer.cli events --seed idea_x
python -m farmer.cli events --seed idea_x --json
python -m farmer.cli doctor
python -m farmer.cli doctor --json
python -m farmer.cli decisions list
python -m farmer.cli report summary
```

## Warehouse Buckets

- `internal_stock`
- `external_candidates`
- `refine_queue`
- `cold_storage`
- `retired`

## Decision Types

- `hire_internal`
- `promote_external`
- `send_to_refinery`
- `hold`
- `retire`

## Data Files

Stored under `apps/farmer/data/` (or `FARMER_DATA_DIR` override):

- `seeds.json`
- `growth_jobs.json`
- `harvests.json`
- `warehouse.json`
- `decisions.json`
- `activity_log.json`

## What Farmer v2 Does Not Do

- Does not autonomously generate production-ready products.
- Does not perform market research.
- Does not act as a background scheduler.
- Does not replace human product judgment.
