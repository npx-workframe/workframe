import { BRAND_ICON, type BrandIconId } from '@/lib/brandAssets'

type SignInBrandIconProps = {
  id: BrandIconId
  className?: string
}

export function SignInBrandIcon({ id, className }: SignInBrandIconProps) {
  return (
    <img
      src={BRAND_ICON[id]}
      alt=""
      className={className ?? 'wf-sign-in-app__brand-img wf-brand-img--theme'}
    />
  )
}
