import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def clean_df():
    np.random.seed(0)
    return pd.DataFrame({
        "id": range(1, 201),
        "age": np.random.randint(18, 65, 200),
        "salary": np.random.normal(60000, 10000, 200),
        "department": np.random.choice(["Engineering", "Sales", "Marketing"], 200),
    })


@pytest.fixture
def messy_df():
    np.random.seed(1)
    n = 300
    df = pd.DataFrame({
        "customer_id": range(1, n + 1),
        "age": np.random.randint(18, 70, n).astype(float),
        "income": np.random.normal(50000, 15000, n),
        "gender": np.random.choice(["Male", "male", "MALE", "Female", "female"], n),
        "constant_col": ["A"] * n,
        "target": np.random.choice([0, 1], n, p=[0.95, 0.05]),
    })
    df.loc[0:15, "age"] = np.nan
    df.loc[3, "age"] = -10
    df = pd.concat([df, df.iloc[0:8]], ignore_index=True)
    return df


@pytest.fixture
def imbalanced_df():
    np.random.seed(2)
    n = 400
    return pd.DataFrame({
        "id": range(n),
        "feature1": np.random.normal(0, 1, n),
        "label": np.random.choice(["no", "yes"], n, p=[0.98, 0.02]),
    })


@pytest.fixture
def high_cardinality_df():
    np.random.seed(3)
    n = 200
    return pd.DataFrame({
        "id": range(n),
        "uuid_col": [f"uid-{i}-{np.random.randint(0, 1_000_000)}" for i in range(n)],
        "value": np.random.normal(0, 1, n),
    })
