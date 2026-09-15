import React from "react";

type DeclarationLike = {
  field: string;
  bounding_box?: { x: number; y: number; width: number; height: number } | null;
};

type Props = {
  imageUrl: string | null;
  declarations: DeclarationLike[];
  selectedField: string | null;
  onSelectField: (field: string | null) => void;
};

/** Evidence image viewer for the District Admin inspect modal. */
export function EvidenceViewer({
  imageUrl,
  declarations,
  selectedField,
  onSelectField,
}: Props) {
  const selected = declarations.find((d) => d.field === selectedField);
  const box = selected?.bounding_box;

  return (
    <div style={{ marginBottom: "var(--space-3)" }}>
      {imageUrl ? (
        <div style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
          <img
            src={imageUrl}
            alt="Captured label evidence"
            style={{ maxWidth: "100%", display: "block", borderRadius: 4 }}
          />
          {box && (
            <div
              style={{
                position: "absolute",
                left: box.x,
                top: box.y,
                width: box.width,
                height: box.height,
                border: "2px solid var(--color-warning, #c9a227)",
                boxSizing: "border-box",
                pointerEvents: "none",
              }}
            />
          )}
        </div>
      ) : (
        <p className="sub">No capture image available for this record.</p>
      )}
      {selectedField && (
        <p className="sub" style={{ marginTop: "var(--space-2)" }}>
          Highlighting field: <strong>{selectedField}</strong>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            style={{ marginLeft: "var(--space-2)" }}
            onClick={() => onSelectField(null)}
          >
            Clear
          </button>
        </p>
      )}
    </div>
  );
}
