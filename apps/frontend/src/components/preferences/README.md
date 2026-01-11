# Dynamic Preferences System

## Overview

The preferences system is built to be **highly extensible and dynamic**. Adding new preferences requires minimal code changes - just update the configuration file.

## Architecture

### 1. Configuration-Driven ([preferences.ts](../config/preferences.ts))

All preference fields are defined in `PREFERENCE_SECTIONS`:

```typescript
{
  id: 'section-id',
  title: 'Section Title',
  description: 'Section description',
  icon: 'IconName',
  fields: [
    {
      key: 'database_field_name',
      label: 'UI Label',
      type: 'slider' | 'number' | 'toggle' | 'multiselect' | 'currency',
      min: 0,
      max: 100,
      step: 5,
      unit: 'miles',
      description: 'Field description',
      defaultValue: null,
    }
  ]
}
```

### 2. Dynamic Components

- **PreferenceFieldInput**: Renders appropriate input based on field type
- **PreferenceSectionCard**: Groups related fields into cards
- **PreferencesPage**: Main page that orchestrates everything

### 3. Type-Safe API

- TypeScript types in [types/preferences.ts](../types/preferences.ts)
- API functions in [api/preferences.ts](../api/preferences.ts)
- Automatic validation and error handling

## Adding New Preferences

### Step 1: Update Backend Model

Add the new field to `UserPreference` model in backend:

```python
new_field: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

### Step 2: Update Backend Schema

Add the field to `UserPreferenceBase` in backend schemas:

```python
new_field: Optional[int] = Field(None, ge=0, le=100)
```

### Step 3: Update Frontend Types

Add to `UserPreferences` interface in [types/preferences.ts](../types/preferences.ts):

```typescript
new_field?: number | null;
```

### Step 4: Add to Configuration

Add to `PREFERENCE_SECTIONS` in [config/preferences.ts](../config/preferences.ts):

```typescript
{
  id: 'existing-section',  // or create new section
  fields: [
    {
      key: 'new_field',
      label: 'New Field',
      type: 'slider',
      min: 0,
      max: 100,
      description: 'What this field does',
      defaultValue: null,
    }
  ]
}
```

**That's it!** The UI will automatically render the new field with proper validation, save functionality, and state management.

## Supported Field Types

| Type          | Description          | Example Use Case     |
| ------------- | -------------------- | -------------------- |
| `slider`      | Slider with min/max  | Walk scores (0-100)  |
| `number`      | Numeric input        | Distance in miles    |
| `currency`    | Number with $ prefix | Price range          |
| `toggle`      | Boolean switch       | Notifications on/off |
| `multiselect` | Multiple selection   | Property types       |
| `select`      | Single selection     | Dropdown options     |

## Features

### Automatic Validation

- Min/max bounds enforced
- Type validation
- Required field handling

### State Management

- Detects unsaved changes
- Shows save/reset buttons
- Optimistic updates with React Query

### User Experience

- Real-time validation
- Clear visual feedback
- Responsive design
- Accessible inputs

## Example: Adding "Pool Preference"

### 1. Backend Model

```python
requires_pool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
```

### 2. Backend Schema

```python
requires_pool: Optional[bool] = None
```

### 3. Frontend Type

```typescript
requires_pool?: boolean | null;
```

### 4. Configuration

```typescript
{
  id: 'property',
  fields: [
    // ...existing fields
    {
      key: 'requires_pool',
      label: 'Requires Pool',
      type: 'toggle',
      description: 'Only show properties with a pool',
      defaultValue: false,
    }
  ]
}
```

Done! The pool preference will now appear in the Property Criteria section.

## Advanced Customization

### Custom Field Types

Add new field types in `PreferenceFieldInput.tsx`:

```typescript
case 'your-custom-type':
  return <YourCustomComponent />;
```

### Custom Validation

Add validation in the `handleBlur` function or create field-specific validators.

### Section Icons

Map new icons in `PreferenceSectionCard.tsx`:

```typescript
const ICON_MAP = {
  YourIcon: <YourIconComponent />,
};
```

## API Integration

The system uses React Query for:

- Automatic caching
- Background refetching
- Optimistic updates
- Error handling

All preference updates are sent to `/api/v1/preferences` with proper authentication.
