import { BRAND_ICON, type BrandIconId } from '@/lib/brandAssets'
import { BrandMark } from '@/components/ui/BrandMark'

type SignInBrandIconProps = {
  id: BrandIconId
  className?: string
}

export function SignInBrandIcon({ id, className }: SignInBrandIconProps) {
  return (
    <BrandMark
      src={BRAND_ICON[id]}
      className={className ?? 'wf-sign-in-app__brand-img wf-brand-img--theme'}
      themeAware={id !== 'workframeColor'}
    />
  )
}
