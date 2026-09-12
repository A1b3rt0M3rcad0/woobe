import { woobeColors } from './src/tokens/colors'
import {
  woobeBreakpoints,
  woobeControl,
  woobeLayers,
  woobeLayout,
  woobeRadius,
  woobeShadow,
  woobeSpacing,
  woobeTypography,
  woobeTypographyScale,
} from './src/tokens'

const woobeTailwindPreset = {
  theme: {
    extend: {
      colors: woobeColors,
      fontFamily: {
        sans: [...woobeTypography.sans],
        mono: [...woobeTypography.mono],
      },
      fontSize: {
        'system-meta': woobeTypographyScale.systemMeta,
        'system-label': woobeTypographyScale.systemLabel,
        'system-control': woobeTypographyScale.systemControl,
        'product-caption': woobeTypographyScale.productCaption,
        'product-small': woobeTypographyScale.productSmall,
        'product-body': woobeTypographyScale.productBody,
        'heading-sm': woobeTypographyScale.headingSmall,
        heading: woobeTypographyScale.heading,
        'heading-lg': woobeTypographyScale.headingLarge,
        metric: woobeTypographyScale.metric,
      },
      spacing: {
        'ui-hairline': woobeSpacing.hairline,
        'ui-xs': woobeSpacing.xs,
        'ui-sm': woobeSpacing.sm,
        'ui-md': woobeSpacing.md,
        'ui-lg': woobeSpacing.lg,
        'ui-xl': woobeSpacing.xl,
        'ui-xxl': woobeSpacing.xxl,
      },
      borderRadius: {
        technical: woobeRadius.technical,
        control: woobeRadius.control,
        container: woobeRadius.container,
      },
      height: {
        'control-segment': woobeControl.height.segment,
        'control-sm': woobeControl.height.compact,
        control: woobeControl.height.default,
        'control-lg': woobeControl.height.large,
        'control-row': woobeControl.height.row,
        'panel-header': woobeControl.height.header,
        'workspace-header': woobeControl.height.workspaceHeader,
      },
      minHeight: {
        'control-segment': woobeControl.height.segment,
        'control-sm': woobeControl.height.compact,
        control: woobeControl.height.default,
        'control-lg': woobeControl.height.large,
        'control-row': woobeControl.height.row,
        'panel-header': woobeControl.height.header,
      },
      width: {
        'project-sidebar': woobeLayout.projectSidebar,
        'playground-rail': woobeLayout.playgroundRail,
        'operations-panel': woobeLayout.operationsPanel,
        inspector: woobeLayout.inspector,
        'inspector-expanded': woobeLayout.inspectorExpanded,
      },
      maxWidth: {
        resource: woobeLayout.resourceMax,
        'resource-wide': woobeLayout.resourceWideMax,
        'dialog-compact': woobeLayout.dialogCompact,
        dialog: woobeLayout.dialogDefault,
        'dialog-wide': woobeLayout.dialogWide,
        inspector: woobeLayout.inspector,
        'inspector-expanded': woobeLayout.inspectorExpanded,
      },
      screens: woobeBreakpoints,
      boxShadow: {
        none: woobeShadow.none,
        popup: woobeShadow.popup,
        overlay: woobeShadow.overlay,
      },
      zIndex: {
        base: woobeLayers.base,
        sticky: woobeLayers.sticky,
        workspace: woobeLayers.workspace,
        popover: woobeLayers.popover,
        overlay: woobeLayers.overlay,
        modal: woobeLayers.modal,
        toast: woobeLayers.toast,
      },
    },
  },
}

export default woobeTailwindPreset
