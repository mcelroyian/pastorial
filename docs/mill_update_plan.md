# Plan: Update Mill Visuals in Pygame

This document outlines the plan to update the visual representation of the Mill in the Pygame project from a simple square to a more detailed design based on an SVG, rendered using Pygame's drawing functions.

**User Requirements Summary:**

*   **Rendering:** Manually re-create the SVG's appearance using Pygame's drawing functions (`draw.rect`, `draw.polygon`, etc.) within the `Mill.draw()` method.
*   **Animation:** No animation for the windmill blades for now.
*   **Colors:** Use the colors as defined in the provided SVG design.
*   **Text Overlays:** Keep the existing text overlays for input/output quantities and processing progress.
*   **Scaling:** The new mill design should fit within the `config.GRID_CELL_SIZE`.

**Concerns & Considerations:**

1.  **Drawing Complexity:** Translating the SVG to Pygame draw calls will be more involved than the current simple rectangle.
    *   **Mitigation:** Structure the code clearly, potentially using helper methods for different components of the mill.
2.  **Coordinate Scaling and Translation:** The SVG's 200x200 viewBox needs to be mapped to Pygame's coordinate system and scaled to fit within `config.GRID_CELL_SIZE`.
    *   **Approach:** Calculate a `scale_factor` and apply it to all SVG coordinates and dimensions. The drawing will be offset by the mill's grid position.
3.  **Color Management:** SVG colors (hex) need to be converted to RGB tuples for Pygame.
    *   **Approach:** Define these RGB color constants in `src/resources/mill.py`.
        *   Base Fill (`#8B5E3C`): `(139, 94, 60)`
        *   Stroke (`#654321`): `(101, 67, 33)`
        *   Roof Fill (`#A0522D`): `(160, 82, 45)`
        *   Door Fill (`#654321`): `(101, 67, 33)`
        *   Windmill Center (`#333`): `(51, 51, 51)`
        *   Blades (`#555`): `(85, 85, 85)`
4.  **Stroke Thickness:** SVG stroke widths also need scaling.
    *   **Approach:** Scale stroke widths by the `scale_factor`, ensuring a minimum of 1 pixel (e.g., `max(1, int(original_stroke_width * scale_factor))`).
5.  **Text Overlay Placement:** The existing text for input/output and progress needs to be legible and well-positioned with the new, more detailed graphic.
    *   **Approach:** Re-implement or adapt the text drawing logic from `ProcessingStation.draw()`. Position text carefully around or offset from the main mill graphic to avoid overlap, ensuring it remains within cell boundaries.
6.  **No Dynamic Color Change (for main body):** Since SVG colors are used, `MILL_COLOR_IDLE` and `MILL_COLOR_PROCESSING` won't directly apply to the mill's body. The `is_processing` state will still be used for the progress text.

**Proposed Implementation Plan (Mermaid Diagram):**

```mermaid
graph TD
    A[Start: Update Mill Visuals] --> B{User Requirements Confirmed};
    B --> C[Phase 1: Implement New Mill.draw() Method in src/resources/mill.py];
    C --> C1[Define SVG-based Color Constants (RGB)];
    C --> C2[Calculate Scaling Factor: scale = GRID_CELL_SIZE / 200.0];
    C --> C3[Implement Drawing for Each Mill Component];
    C3 --> C3a[Draw Mill Base (pygame.draw.rect)];
    C3 --> C3b[Draw Roof (pygame.draw.polygon)];
    C3 --> C3c[Draw Door (pygame.draw.rect)];
    C3 --> C3d[Draw Windmill Center (pygame.draw.circle)];
    C3 --> C3e[Draw Blades (pygame.draw.line x4)];
    C --> C4[Integrate Text Overlays];
    C4 --> C4a[Adapt text rendering logic from ProcessingStation];
    C4 --> C4b[Adjust text positions for clarity with new graphic];
    C --> D[Phase 2: Testing & Refinement];
    D --> D1[Visually verify appearance (idle/processing)];
    D --> D2[Ensure text is legible and well-placed];
    D --> D3[Review code for clarity and use of constants];
    D --> E{Plan Review Complete};
    E --> F[End];
```

**Detailed Steps:**

1.  **Modify `src/resources/mill.py`:**
    *   **Import `pygame` and `config`** as needed.
    *   **Define Color Constants:** Add the RGB color tuples derived from the SVG hex codes.
    *   **Override the `draw(self, surface: pygame.Surface, font: pygame.font.Font)` method:**
        *   This method will *not* call `super().draw()`.
        *   Calculate `cell_rect_x = self.position.x * config.GRID_CELL_SIZE` and `cell_rect_y = self.position.y * config.GRID_CELL_SIZE`.
        *   Calculate `scale_factor = config.GRID_CELL_SIZE / 200.0`.
        *   **Draw Mill Components:**
            *   For each SVG element (base, roof, door, center, blades):
                *   Translate its SVG coordinates (`x`, `y`, `cx`, `cy`, points, etc.) and dimensions (`width`, `height`, `r`) by multiplying with `scale_factor`.
                *   Add `cell_rect_x` and `cell_rect_y` to the scaled coordinates to position them correctly within the grid cell.
                *   Use the appropriate `pygame.draw` function with the calculated coordinates, dimensions, and defined colors.
                *   Scale stroke widths: `max(1, int(svg_stroke_width * scale_factor))`.
        *   **Draw Text Information:**
            *   Replicate the logic from `ProcessingStation.draw()` for creating text surfaces for input, output, and progress.
            *   Adjust the positioning of these text surfaces (e.g., top/bottom of the cell, centered horizontally, or offset to avoid clashing with the mill graphic).

2.  **Testing:**
    *   Run the game to visually inspect the new mill.
    *   Check its appearance when idle and when processing (to ensure progress text appears correctly).
    *   Verify that text overlays are clear, legible, and don't obstruct important parts of the mill graphic.
    *   Ensure the mill fits correctly within the grid cell.