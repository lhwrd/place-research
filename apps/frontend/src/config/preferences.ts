/**
 * Preference field configuration
 * This file defines all preference fields in a centralized, dynamic way
 * Add new preferences here to automatically render them in the UI
 */

export type PreferenceFieldType =
  | 'number'
  | 'range'
  | 'slider'
  | 'select'
  | 'multiselect'
  | 'toggle'
  | 'currency';

export interface PreferenceField {
  key: string;
  label: string;
  type: PreferenceFieldType;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  description?: string;
  options?: Array<{ value: string; label: string }>;
  placeholder?: string;
  defaultValue?: string | number | boolean | string[] | null;
}

export interface PreferenceSection {
  id: string;
  title: string;
  description: string;
  icon: string;
  fields: PreferenceField[];
}

/**
 * Centralized preference configuration
 * Add new sections and fields here to extend the preferences UI
 */
export const PREFERENCE_SECTIONS: PreferenceSection[] = [
  {
    id: 'walkability',
    title: 'Walkability & Transportation',
    description: 'Set minimum scores for walkability, bikeability, and transit access',
    icon: 'Walk',
    fields: [
      {
        key: 'min_walk_score',
        label: 'Minimum Walk Score',
        type: 'slider',
        min: 0,
        max: 100,
        step: 5,
        description: 'Properties must have at least this walk score',
        defaultValue: null,
      },
      {
        key: 'min_bike_score',
        label: 'Minimum Bike Score',
        type: 'slider',
        min: 0,
        max: 100,
        step: 5,
        description: 'Properties must have at least this bike score',
        defaultValue: null,
      },
      {
        key: 'min_transit_score',
        label: 'Minimum Transit Score',
        type: 'slider',
        min: 0,
        max: 100,
        step: 5,
        description: 'Properties must have at least this transit score',
        defaultValue: null,
      },
    ],
  },
  {
    id: 'amenities',
    title: 'Nearby Amenities',
    description: 'Set maximum distances to important amenities',
    icon: 'MapPin',
    fields: [
      {
        key: 'max_grocery_distance',
        label: 'Grocery Stores',
        type: 'number',
        min: 0,
        max: 20,
        step: 0.5,
        unit: 'miles',
        description: 'Maximum distance to nearest grocery store',
        placeholder: 'e.g., 2.0',
        defaultValue: 2.0,
      },
      {
        key: 'max_park_distance',
        label: 'Parks',
        type: 'number',
        min: 0,
        max: 10,
        step: 0.5,
        unit: 'miles',
        description: 'Maximum distance to nearest park',
        placeholder: 'e.g., 1.0',
        defaultValue: 1.0,
      },
      {
        key: 'max_school_distance',
        label: 'Schools',
        type: 'number',
        min: 0,
        max: 20,
        step: 0.5,
        unit: 'miles',
        description: 'Maximum distance to nearest school',
        placeholder: 'e.g., 3.0',
        defaultValue: 3.0,
      },
      {
        key: 'max_hospital_distance',
        label: 'Hospitals',
        type: 'number',
        min: 0,
        max: 50,
        step: 1,
        unit: 'miles',
        description: 'Maximum distance to nearest hospital',
        placeholder: 'e.g., 10.0',
        defaultValue: 10.0,
      },
    ],
  },
  {
    id: 'property',
    title: 'Property Criteria',
    description: 'Define your ideal property specifications',
    icon: 'Home',
    fields: [
      {
        key: 'min_bedrooms',
        label: 'Minimum Bedrooms',
        type: 'number',
        min: 0,
        max: 10,
        step: 1,
        description: 'Minimum number of bedrooms',
        placeholder: 'e.g., 3',
        defaultValue: null,
      },
      {
        key: 'min_bathrooms',
        label: 'Minimum Bathrooms',
        type: 'number',
        min: 0,
        max: 10,
        step: 0.5,
        description: 'Minimum number of bathrooms',
        placeholder: 'e.g., 2.0',
        defaultValue: null,
      },
      {
        key: 'min_square_feet',
        label: 'Minimum Square Feet',
        type: 'number',
        min: 0,
        max: 10000,
        step: 100,
        unit: 'sq ft',
        description: 'Minimum property size in square feet',
        placeholder: 'e.g., 1500',
        defaultValue: null,
      },
      {
        key: 'max_year_built',
        label: 'Built After Year',
        type: 'number',
        min: 1800,
        max: new Date().getFullYear(),
        step: 1,
        description: 'Properties must be built after this year',
        placeholder: 'e.g., 1990',
        defaultValue: null,
      },
      {
        key: 'preferred_property_types',
        label: 'Property Types',
        type: 'multiselect',
        description: 'Preferred property types',
        options: [
          { value: 'Single Family', label: 'Single Family Home' },
          { value: 'Townhouse', label: 'Townhouse' },
          { value: 'Condo', label: 'Condominium' },
          { value: 'Multi-Family', label: 'Multi-Family' },
          { value: 'Apartment', label: 'Apartment' },
        ],
        defaultValue: [],
      },
    ],
  },
  {
    id: 'budget',
    title: 'Budget',
    description: 'Set your price range',
    icon: 'DollarSign',
    fields: [
      {
        key: 'min_price',
        label: 'Minimum Price',
        type: 'currency',
        min: 0,
        step: 10000,
        description: 'Minimum property price',
        placeholder: 'e.g., 300000',
        defaultValue: null,
      },
      {
        key: 'max_price',
        label: 'Maximum Price',
        type: 'currency',
        min: 0,
        step: 10000,
        description: 'Maximum property price',
        placeholder: 'e.g., 800000',
        defaultValue: null,
      },
    ],
  },
  {
    id: 'commute',
    title: 'Commute',
    description: 'Set maximum commute times',
    icon: 'Car',
    fields: [
      {
        key: 'max_commute_time',
        label: 'Maximum Commute Time',
        type: 'number',
        min: 0,
        max: 180,
        step: 5,
        unit: 'minutes',
        description: 'Maximum acceptable commute time',
        placeholder: 'e.g., 45',
        defaultValue: null,
      },
    ],
  },
  {
    id: 'notifications',
    title: 'Notifications',
    description: 'Manage your notification preferences',
    icon: 'Bell',
    fields: [
      {
        key: 'notify_new_listings',
        label: 'New Listings',
        type: 'toggle',
        description: 'Get notified about new property listings matching your criteria',
        defaultValue: false,
      },
      {
        key: 'notify_price_changes',
        label: 'Price Changes',
        type: 'toggle',
        description: 'Get notified when saved property prices change',
        defaultValue: false,
      },
    ],
  },
];

/**
 * Get all preference keys
 */
export const getAllPreferenceKeys = (): string[] => {
  return PREFERENCE_SECTIONS.flatMap(section =>
    section.fields.map(field => field.key)
  );
};

/**
 * Get field configuration by key
 */
export const getFieldConfig = (key: string): PreferenceField | undefined => {
  for (const section of PREFERENCE_SECTIONS) {
    const field = section.fields.find(f => f.key === key);
    if (field) return field;
  }
  return undefined;
};
