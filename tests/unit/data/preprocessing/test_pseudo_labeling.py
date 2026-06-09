"""Tests for pseudo_labeling — label assignment correctness.

"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data.preprocessing.training_dataset.pseudo_labeling import assign_pseudo_labels


class TestAssignPseudoLabels:
    """Tests for assign_pseudo_labels."""

    @staticmethod
    def _make_active_df(n: int = 50) -> pd.DataFrame:
        """Build a synthetic active DataFrame."""
        np.random.seed(42)
        return pd.DataFrame({
            "cms_code_enc": [f"CMS_{i}" for i in range(n)],
            "ewma": np.random.uniform(0, 100, n),
            "delta_ewma": np.random.uniform(-10, 10, n),
            "recency_days": np.random.randint(1, 200, n),
            "item_avg": np.random.uniform(5, 50, n),
            "item_last": np.random.uniform(0, 50, n),
            "sim_score": np.zeros(n),  # Will be overwritten
        })

    def test_confirmed_overrides_all(self):
        """Confirmed IDs should always be labeled 'confirmed'."""
        df = self._make_active_df()
        eval_ids = {"CMS_0", "CMS_1", "CMS_2"}
        result = assign_pseudo_labels(
            df,
            prototype={},  # Empty prototype → sim_score = 0
            eval_ids=eval_ids,
            sim_threshold=0.5,
            recency_reliable_neg=30,
        )
        confirmed = result[result["cms_code_enc"].isin(eval_ids)]
        assert (confirmed["label_source"] == "confirmed").all()

    def test_holdout_confirmed_gets_eval_label(self):
        """Holdout confirmed IDs should be labeled separately for eval only."""
        df = self._make_active_df()
        result = assign_pseudo_labels(
            df,
            prototype={},
            eval_ids={"CMS_0"},
            sim_threshold=0.5,
            recency_reliable_neg=30,
            holdout_eval_ids={"CMS_1"},
        )
        assert result.loc[result["cms_code_enc"] == "CMS_0", "label_source"].iloc[0] == "confirmed"
        assert result.loc[result["cms_code_enc"] == "CMS_1", "label_source"].iloc[0] == "confirmed_eval"

    def test_no_overlap_between_categories(self):
        """Each row should have exactly one label_source."""
        df = self._make_active_df()
        result = assign_pseudo_labels(
            df,
            prototype={},
            eval_ids=set(),
            sim_threshold=0.5,
            recency_reliable_neg=30,
        )
        valid_labels = {"confirmed", "confirmed_eval", "pseudo_churn", "reliable_neg", "pu_unlabeled"}
        assert set(result["label_source"].unique()).issubset(valid_labels)

    def test_adds_sim_score_column(self):
        """Should add sim_score column."""
        df = self._make_active_df()
        result = assign_pseudo_labels(
            df,
            prototype={},
            eval_ids=set(),
            sim_threshold=0.5,
            recency_reliable_neg=30,
        )
        assert "sim_score" in result.columns
        assert "label_source" in result.columns

    def test_does_not_modify_input(self):
        """Should return new DataFrame, not modify input."""
        df = self._make_active_df()
        original_cols = set(df.columns)
        _ = assign_pseudo_labels(
            df,
            prototype={},
            eval_ids=set(),
            sim_threshold=0.5,
            recency_reliable_neg=30,
        )
        assert set(df.columns) == original_cols
