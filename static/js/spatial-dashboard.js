/** Polygon selection for evidence-first signifier exploration. */
(function () {
    function normalizedPoint(svg, event) {
        var bounds = svg.getBoundingClientRect();
        return {
            x: (((event.clientX - bounds.left) / bounds.width) * 200 - 10) / 180,
            y: (((event.clientY - bounds.top) / bounds.height) * 180 - 10) / 160,
        };
    }

    function insideTriad(point) {
        return point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1 &&
            Math.abs(point.x - 0.5) <= point.y / 2;
    }

    function renderStories(payload) {
        var target = document.getElementById('spatial-story-results');
        target.replaceChildren();
        if (!payload.stories.length) {
            target.textContent = 'No stories fall inside this selection.';
            return;
        }
        payload.stories.forEach(function (story) {
            var article = document.createElement('article');
            article.className = 'spatial-story-card';
            var heading = document.createElement('h4');
            heading.textContent = story.headline || 'Participant story';
            var excerpt = document.createElement('p');
            excerpt.textContent = story.story_excerpt;
            article.append(heading, excerpt);
            target.appendChild(article);
        });
    }

    function clearSelection(figure, clearResults) {
        figure.dataset.selectionPoints = '[]';
        figure.dataset.selectionComplete = 'false';
        figure.querySelectorAll('.selection-vertex').forEach(function (marker) {
            marker.remove();
        });
        figure.querySelector('.selection-outline').setAttribute('points', '');
        if (clearResults) {
            document.getElementById('spatial-story-results').replaceChildren();
        }
    }

    function svgCoordinates(point) {
        return (10 + point.x * 180) + ',' + (10 + point.y * 160);
    }

    function querySelection(figure, points) {
        figure.dataset.selectionComplete = 'true';
        fetch('/api/signifiers/' + encodeURIComponent(figure.dataset.signifierId) + '/stories/query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({selection: {kind: 'polygon', points: points}}),
        })
            .then(function (response) {
                if (!response.ok) throw new Error('Spatial query failed');
                return response.json();
            })
            .then(renderStories)
            .catch(function () {
                document.getElementById('spatial-story-results').textContent =
                    'Story selection is temporarily unavailable.';
            });
    }

    function addSelectionPoint(figure, point) {
        if (!insideTriad(point)) return;
        if (figure.dataset.selectionComplete === 'true') {
            clearSelection(figure, false);
        }
        var points = JSON.parse(figure.dataset.selectionPoints || '[]');
        points.push({x: Number(point.x.toFixed(4)), y: Number(point.y.toFixed(4))});
        figure.dataset.selectionPoints = JSON.stringify(points);

        var svg = figure.querySelector('svg');
        var marker = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        marker.setAttribute('class', 'selection-vertex');
        marker.setAttribute('cx', String(10 + point.x * 180));
        marker.setAttribute('cy', String(10 + point.y * 160));
        marker.setAttribute('r', '4');
        svg.appendChild(marker);
        figure.querySelector('.selection-outline').setAttribute(
            'points', points.map(svgCoordinates).join(' ')
        );

        if (points.length === 3) querySelection(figure, points);
    }

    document.addEventListener('click', function (event) {
        var clearButton = event.target.closest('.clear-spatial-selection');
        if (clearButton) {
            clearSelection(clearButton.closest('.signifier-plot'), true);
            return;
        }
        var svg = event.target.closest('.signifier-plot svg');
        if (!svg) return;
        var figure = svg.closest('.signifier-plot');
        var point = event.target.classList.contains('spatial-story-point') ? {
            x: Number(event.target.dataset.x),
            y: Number(event.target.dataset.y),
        } : normalizedPoint(svg, event);
        addSelectionPoint(figure, point);
    });

    document.addEventListener('keydown', function (event) {
        if (!event.target.classList.contains('spatial-story-point') ||
            (event.key !== 'Enter' && event.key !== ' ')) return;
        event.preventDefault();
        addSelectionPoint(event.target.closest('.signifier-plot'), {
            x: Number(event.target.dataset.x),
            y: Number(event.target.dataset.y),
        });
    });
}());
