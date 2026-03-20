/**
 * Triad canvas interaction.
 *
 * For each .triad-canvas SVG:
 * - Clicking inside the triangle moves the marker to that point
 * - Dragging the marker repositions it
 * - Coordinates are normalised to [0,1] and written to hidden form inputs
 *
 * Triangle vertices (SVG coordinates):
 *   top:          (100, 10)
 *   bottom-left:  (10,  170)
 *   bottom-right: (190, 170)
 *
 * Normalisation: x = (svgX - 10) / 180, y = (svgY - 10) / 160
 * Clamped to [0, 1].
 *
 * Initial marker position: cx=100, cy=90 → normalised (0.5, 0.5)
 */

// Exported so the page can call resetTriadMarkers() after form reset
var resetTriadMarkers;  // eslint-disable-line no-var

(function () {
    // Bounding box of the triangle used for coordinate normalisation
    const X_MIN = 10, X_RANGE = 180;
    const Y_MIN = 10, Y_RANGE = 160;

    // Triangle vertices for point-in-triangle test
    const V = [
        { x: 100, y: 10  },
        { x: 10,  y: 170 },
        { x: 190, y: 170 },
    ];

    function sign(p, a, b) {
        return (p.x - b.x) * (a.y - b.y) - (a.x - b.x) * (p.y - b.y);
    }

    function pointInTriangle(p) {
        const d1 = sign(p, V[0], V[1]);
        const d2 = sign(p, V[1], V[2]);
        const d3 = sign(p, V[2], V[0]);
        const hasNeg = (d1 < 0) || (d2 < 0) || (d3 < 0);
        const hasPos = (d1 > 0) || (d2 > 0) || (d3 > 0);
        return !(hasNeg && hasPos);
    }

    function clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    /** Convert SVG coordinates to normalised [0,1] floats. */
    function toNorm(svgX, svgY) {
        return {
            x: parseFloat(clamp((svgX - X_MIN) / X_RANGE, 0, 1).toFixed(3)),
            y: parseFloat(clamp((svgY - Y_MIN) / Y_RANGE, 0, 1).toFixed(3)),
        };
    }

    /** Get SVG-space cursor position from a pointer event. */
    function svgPoint(svg, evt) {
        const pt = svg.createSVGPoint();
        pt.x = evt.clientX;
        pt.y = evt.clientY;
        return pt.matrixTransform(svg.getScreenCTM().inverse());
    }

    /** Move the marker to (svgX, svgY) and update hidden inputs. */
    function moveMarker(svg, marker, svgX, svgY) {
        marker.setAttribute('cx', svgX);
        marker.setAttribute('cy', svgY);

        const triadId = svg.dataset.triadId;
        const norm = toNorm(svgX, svgY);
        document.querySelector(`input[name="${triadId}_x"]`).value = norm.x;
        document.querySelector(`input[name="${triadId}_y"]`).value = norm.y;
    }

    document.querySelectorAll('.triad-canvas').forEach(function (svg) {
        const marker = svg.querySelector('.triad-marker');
        let dragging = false;

        svg.addEventListener('click', function (evt) {
            if (dragging) return;
            const p = svgPoint(svg, evt);
            if (!pointInTriangle(p)) return;
            moveMarker(svg, marker, p.x, p.y);
        });

        marker.addEventListener('mousedown', function (evt) {
            dragging = true;
            evt.preventDefault();
        });

        document.addEventListener('mousemove', function (evt) {
            if (!dragging) return;
            const p = svgPoint(svg, evt);
            if (!pointInTriangle(p)) return;
            moveMarker(svg, marker, p.x, p.y);
        });

        document.addEventListener('mouseup', function () {
            dragging = false;
        });

        // Touch support
        marker.addEventListener('touchstart', function (evt) {
            dragging = true;
            evt.preventDefault();
        }, { passive: false });

        document.addEventListener('touchmove', function (evt) {
            if (!dragging) return;
            const touch = evt.touches[0];
            const p = svgPoint(svg, touch);
            if (!pointInTriangle(p)) return;
            moveMarker(svg, marker, p.x, p.y);
        }, { passive: true });

        document.addEventListener('touchend', function () {
            dragging = false;
        });
    });

    // Reset all markers to initial position (0.5, 0.5) → cx=100, cy=90
    resetTriadMarkers = function () {
        document.querySelectorAll('.triad-canvas').forEach(function (svg) {
            var marker = svg.querySelector('.triad-marker');
            moveMarker(svg, marker, 100, 90);
        });
    };
}());
