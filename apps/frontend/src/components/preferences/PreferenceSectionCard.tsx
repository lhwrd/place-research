/**
 * Preference section component
 * Renders a group of related preference fields
 */
import {
  Card,
  CardContent,
  Box,
  Typography,
  Divider,
  Grid,
} from "@mui/material";
import { Home, MapPin, DollarSign, Bell, Car, Footprints } from "lucide-react";
import { PreferenceSection } from "@/config/preferences";
import { PreferenceFieldInput } from "./PreferenceFieldInput";

interface PreferenceSectionCardProps {
  section: PreferenceSection;
  values: Record<string, any>;
  onChange: (key: string, value: any) => void;
  disabled?: boolean;
}

const ICON_MAP: Record<string, React.ReactNode> = {
  Walk: <Footprints size={20} />,
  MapPin: <MapPin size={20} />,
  Home: <Home size={20} />,
  DollarSign: <DollarSign size={20} />,
  Bell: <Bell size={20} />,
  Car: <Car size={20} />,
};

export const PreferenceSectionCard: React.FC<PreferenceSectionCardProps> = ({
  section,
  values,
  onChange,
  disabled = false,
}) => {
  return (
    <Card>
      <CardContent>
        {/* Section Header */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1 }}>
          <Box sx={{ color: "primary.main" }}>
            {ICON_MAP[section.icon] || <Home size={20} />}
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" fontWeight="600">
              {section.title}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {section.description}
            </Typography>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Fields */}
        <Grid container spacing={3}>
          {section.fields.map((field) => (
            <Grid
              item
              xs={12}
              sm={field.type === "toggle" ? 12 : 6}
              key={field.key}
            >
              <Box>
                {field.type !== "toggle" && (
                  <Typography variant="body2" fontWeight="500" sx={{ mb: 0.5 }}>
                    {field.label}
                  </Typography>
                )}
                {field.type !== "toggle" && field.description && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: "block", mb: 1 }}
                  >
                    {field.description}
                  </Typography>
                )}
                <PreferenceFieldInput
                  field={field}
                  value={values[field.key]}
                  onChange={onChange}
                  disabled={disabled}
                />
              </Box>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );
};
