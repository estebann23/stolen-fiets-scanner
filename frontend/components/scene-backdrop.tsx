export function SceneBackdrop() {
  return (
    <div className="scene-backdrop" aria-hidden="true">
      <div className="scene-backdrop-wash" />
      <div className="scene-backdrop-horizon">
        <div className="scene-backdrop-grid" />
      </div>
      <div className="scene-backdrop-vignette" />
    </div>
  )
}
