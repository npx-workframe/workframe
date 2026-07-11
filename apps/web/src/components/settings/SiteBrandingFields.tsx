import { useCallback, useEffect, useState } from 'react'

import { SignInAppField } from '@/components/settings/SignInAppField'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PanelInlineNotice } from '@/components/ui/PanelPrimitives'
import { applySiteMeta, fetchPublicSiteMeta } from '@/lib/siteMeta'
import { formatWorkframeErrorMessage } from '@/lib/workframeErrors'
import { workframeAuthApi } from '@/lib/workframeAuthApi'

type SiteBrandingFieldsProps = {
  disabled?: boolean
  onStatus?: (message: string) => void
}

async function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error ?? new Error('read_failed'))
    reader.readAsDataURL(file)
  })
}

export function SiteBrandingFields({ disabled, onStatus }: SiteBrandingFieldsProps) {
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [themeColor, setThemeColor] = useState('#0A0A0F')
  const [hasOg, setHasOg] = useState(false)
  const [hasFavicon, setHasFavicon] = useState(false)

  useEffect(() => {
    void workframeAuthApi.getInstallStack().then((cfg) => {
      const branding = cfg.site_branding
      if (branding?.title) setTitle(branding.title)
      if (branding?.description) setDescription(branding.description)
      if (branding?.theme_color) setThemeColor(branding.theme_color)
      setHasOg(Boolean(branding?.has_og_image))
      setHasFavicon(Boolean(branding?.has_favicon))
    }).catch(() => {})
  }, [])

  const saveText = useCallback(async () => {
    setError(null)
    try {
      await workframeAuthApi.patchInstallStack({
        site_branding: {
          title: title.trim(),
          description: description.trim(),
          theme_color: themeColor.trim(),
        },
      })
      onStatus?.('Web presence settings saved.')
      const meta = await fetchPublicSiteMeta()
      if (meta?.ok) applySiteMeta(meta)
      return true
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Save web presence'))
      return false
    }
  }, [description, onStatus, themeColor, title])

  const uploadAsset = async (kind: 'og' | 'favicon', file: File | null) => {
    if (!file || disabled) return
    setError(null)
    try {
      const dataUrl = await readFileAsDataUrl(file)
      const result = await workframeAuthApi.uploadSiteBrandingAsset({ kind, data_base64: dataUrl })
      if (!result.ok) {
        setError(result.error || `Upload failed for ${kind}`)
        return
      }
      if (kind === 'og') setHasOg(true)
      if (kind === 'favicon') setHasFavicon(true)
      onStatus?.(kind === 'og' ? 'OG image uploaded.' : 'Favicon uploaded.')
      const meta = await fetchPublicSiteMeta()
      if (meta?.ok) applySiteMeta(meta)
      await saveText()
    } catch (err) {
      setError(formatWorkframeErrorMessage(err, 'Upload branding asset'))
    }
  }

  return (
    <div className="wf-onboarding-form space-y-4">
      {error ? <PanelInlineNotice>{error}</PanelInlineNotice> : null}
      <p className="wf-wizard-section__hint m-0">
        Link previews, mobile home-screen install, and browser tab branding. Leave title and description blank to use your
        workframe name and mission from above.
      </p>
      <div className="wf-sign-in-app__grid">
        <SignInAppField label="Public title override" htmlFor="wf-site-title">
          <Input
            id="wf-site-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Defaults to workframe name"
            disabled={disabled}
          />
        </SignInAppField>
        <SignInAppField label="Theme color" htmlFor="wf-site-theme">
          <Input
            id="wf-site-theme"
            value={themeColor}
            onChange={(e) => setThemeColor(e.target.value)}
            placeholder="#0A0A0F"
            disabled={disabled}
          />
        </SignInAppField>
      </div>
      <SignInAppField label="Public description override" htmlFor="wf-site-description" fullWidth>
        <Input
          id="wf-site-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Defaults to mission statement"
          disabled={disabled}
        />
      </SignInAppField>
      <div className="wf-sign-in-app__grid">
        <SignInAppField
          label="OG / share image"
          htmlFor="wf-site-og"
          hint={hasOg ? 'Custom image uploaded.' : 'Uses workframe logo or default until you upload (1200×630 recommended).'}
        >
          <Input
            id="wf-site-og"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            disabled={disabled}
            onChange={(e) => void uploadAsset('og', e.target.files?.[0] ?? null)}
          />
        </SignInAppField>
        <SignInAppField
          label="Favicon"
          htmlFor="wf-site-favicon"
          hint={hasFavicon ? 'Custom favicon uploaded.' : 'Defaults to Workframe favicon.'}
        >
          <Input
            id="wf-site-favicon"
            type="file"
            accept="image/png,image/svg+xml,image/x-icon"
            disabled={disabled}
            onChange={(e) => void uploadAsset('favicon', e.target.files?.[0] ?? null)}
          />
        </SignInAppField>
      </div>
      <div className="flex justify-end">
        <Button type="button" variant="default" disabled={disabled} onClick={() => void saveText()}>
          Save web presence
        </Button>
      </div>
    </div>
  )
}
