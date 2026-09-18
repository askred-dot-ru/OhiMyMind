import { Logo } from "./Logo";
import { PRODUCT_NAME } from "./brand";

export function BrandSplash({ onClose }: { onClose: () => void }) {
  return (
    <div className="splash" role="dialog" aria-modal="true" aria-label={PRODUCT_NAME}>
      <div className="splash-blur" />
      <div className="splash-stage">
        <Logo className="logo splash-logo" alive />
        <div className="splash-name">{PRODUCT_NAME}</div>
        <button type="button" className="primary splash-back" onClick={onClose}>
          Вернуться
        </button>
      </div>
    </div>
  );
}
