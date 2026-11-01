import shared from '../../../design/tokens.json'
import appearance from './theme.json'

// UI appearance only. Clinical colours remain owned by the shared model/report tokens.
export default {
  ...shared, ...appearance,
  font: { ...shared.font, ...appearance.font },
  color: { ...shared.color, ...appearance.color },
}
