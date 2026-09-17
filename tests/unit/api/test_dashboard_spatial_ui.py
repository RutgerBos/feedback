"""Dashboard spatial-exploration rendering tests."""


def test_dashboard_fragment_leads_with_signifier_story_distribution():
    from src.api.ui import _templates
    from src.services.dashboard import DashboardData

    data = DashboardData(
        total_stories=1,
        signifier_distributions=[
            {
                "signifier_id": "workflow_nature",
                "stories": [
                    {
                        "story_id": "story-1",
                        "headline": "Blocked by CI",
                        "x": 0.3,
                        "y": 0.6,
                    }
                ],
            }
        ],
    )

    html = _templates.get_template("_dashboard_data.html").render(data=data)

    spatial_position = html.index("Explore stories by signifier")
    themes_position = html.index("Top Themes")
    assert spatial_position < themes_position
    assert 'data-signifier-id="workflow_nature"' in html
    assert 'data-story-id="story-1"' in html
    assert 'data-x="0.3"' in html
    assert 'data-y="0.6"' in html
    assert "Blocked by CI" in html
