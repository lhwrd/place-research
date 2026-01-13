// Re-exporting MUI Card components for convenience
export {
  Card,
  CardHeader,
  CardContent,
  CardActions as CardAction,
  CardActions as CardFooter,
} from "@mui/material";

// MUI doesn't have CardTitle and CardDescription as separate components
// They use Typography within CardHeader
// If needed, create custom wrappers here
import { Typography, TypographyProps } from "@mui/material";

export const CardTitle = (props: TypographyProps) => (
  <Typography variant="h6" component="div" {...props} />
);

export const CardDescription = (props: TypographyProps) => (
  <Typography variant="body2" color="text.secondary" {...props} />
);
