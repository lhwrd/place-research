/**
 * Dynamic preference field component
 * Renders different input types based on field configuration
 */
import { useState } from "react";
import {
  Box,
  TextField,
  Slider,
  Typography,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  Chip,
  OutlinedInput,
  InputAdornment,
} from "@mui/material";
import { PreferenceField } from "@/config/preferences";

interface PreferenceFieldInputProps {
  field: PreferenceField;
  value: string | number | boolean | string[] | undefined;
  onChange: (
    key: string,
    value: string | number | boolean | string[] | undefined
  ) => void;
  disabled?: boolean;
}

export const PreferenceFieldInput: React.FC<PreferenceFieldInputProps> = ({
  field,
  value,
  onChange,
  disabled = false,
}) => {
  const [localValue, setLocalValue] = useState(value ?? field.defaultValue);

  const handleChange = (
    newValue: string | number | boolean | string[] | undefined
  ) => {
    setLocalValue(newValue);
    onChange(field.key, newValue);
  };

  const handleBlur = () => {
    // Ensure value is within bounds for number inputs
    if (field.type === "number" || field.type === "currency") {
      let numValue =
        typeof localValue === "number"
          ? localValue
          : typeof localValue === "string"
          ? parseFloat(localValue)
          : field.min ?? 0;
      if (isNaN(numValue)) {
        numValue =
          typeof field.defaultValue === "number"
            ? field.defaultValue
            : field.min ?? 0;
      } else {
        if (field.min !== undefined) numValue = Math.max(field.min, numValue);
        if (field.max !== undefined) numValue = Math.min(field.max, numValue);
      }
      if (numValue !== localValue) {
        setLocalValue(numValue);
        onChange(field.key, numValue);
      }
    }
  };

  // Render based on field type
  switch (field.type) {
    case "slider":
      return (
        <Box sx={{ px: 1 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {field.min ?? 0}
            </Typography>
            <Typography variant="body2" fontWeight="600">
              {localValue ?? "Not set"}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {field.max ?? 100}
            </Typography>
          </Box>
          <Slider
            value={typeof localValue === "number" ? localValue : field.min ?? 0}
            onChange={(_, newValue) =>
              handleChange(Array.isArray(newValue) ? newValue[0] : newValue)
            }
            min={field.min ?? 0}
            max={field.max ?? 100}
            step={field.step ?? 1}
            disabled={disabled}
            valueLabelDisplay="auto"
            marks={[
              { value: field.min ?? 0, label: "" },
              { value: field.max ?? 100, label: "" },
            ]}
          />
        </Box>
      );

    case "number":
      return (
        <TextField
          fullWidth
          type="number"
          value={localValue ?? ""}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={handleBlur}
          disabled={disabled}
          placeholder={field.placeholder}
          InputProps={{
            endAdornment: field.unit ? (
              <InputAdornment position="end">{field.unit}</InputAdornment>
            ) : undefined,
            inputProps: {
              min: field.min,
              max: field.max,
              step: field.step ?? 1,
            },
          }}
          size="small"
        />
      );

    case "currency":
      return (
        <TextField
          fullWidth
          type="number"
          value={localValue ?? ""}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={handleBlur}
          disabled={disabled}
          placeholder={field.placeholder}
          InputProps={{
            startAdornment: <InputAdornment position="start">$</InputAdornment>,
            inputProps: {
              min: field.min,
              max: field.max,
              step: field.step ?? 1000,
            },
          }}
          size="small"
        />
      );

    case "toggle":
      return (
        <FormControlLabel
          control={
            <Switch
              checked={!!localValue}
              onChange={(e) => handleChange(e.target.checked)}
              disabled={disabled}
            />
          }
          label={field.description || ""}
        />
      );

    case "multiselect":
      return (
        <Select
          fullWidth
          multiple
          value={localValue ?? []}
          onChange={(e) => handleChange(e.target.value as string[])}
          disabled={disabled}
          input={<OutlinedInput />}
          renderValue={(selected) => (
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {(selected as string[]).map((val) => {
                const option = field.options?.find((opt) => opt.value === val);
                return (
                  <Chip key={val} label={option?.label || val} size="small" />
                );
              })}
            </Box>
          )}
          size="small"
        >
          {field.options?.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </Select>
      );

    case "select":
      return (
        <Select
          fullWidth
          value={localValue ?? ""}
          onChange={(e) => handleChange(e.target.value)}
          disabled={disabled}
          size="small"
        >
          {field.options?.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </Select>
      );

    default:
      return (
        <TextField
          fullWidth
          value={localValue ?? ""}
          onChange={(e) => handleChange(e.target.value)}
          disabled={disabled}
          placeholder={field.placeholder}
          size="small"
        />
      );
  }
};
