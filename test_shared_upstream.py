import joint_process_doe as joint


def recipe(name, upstream=0):
    values = {key: 0 for key in joint.SPACE}
    for key in joint.UPSTREAM_FACTORS:
        values[key] = upstream
    values.update(name=name, recipe_hash=name, recipe_id=0)
    return values


def test_grouped_tasks_share_only_identical_upstream_recipes():
    first = recipe("first")
    downstream_variant = recipe("downstream_variant")
    downstream_variant["fill_thick"] = 1
    other_upstream = recipe("other_upstream", upstream=1)
    groups = joint.grouped_tasks([first, downstream_variant, other_upstream], 2, set())
    sizes = sorted(len(recipes) for _, recipes in groups)
    assert sizes == [1, 1, 2, 2]


if __name__ == "__main__":
    test_grouped_tasks_share_only_identical_upstream_recipes()
    print("shared-upstream grouping checks: PASS")
