/**
 * Custom form hook using React Hook Form and Zod (works with Zod v4 + RHF v7)
 */
import {
  useForm as useReactHookForm,
  type UseFormProps,
  type FieldValues,
  type Resolver,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

/**
 * Constrain schema to object-ish values for RHF.
 * Zod v4 uses ZodType<Output, Input>.
 */
type RHFSchema = z.ZodType<FieldValues, FieldValues>;

export interface UseFormOptions<TSchema extends RHFSchema>
  extends Omit<UseFormProps<z.input<TSchema>>, "resolver"> {
  schema: TSchema;
}

export const useForm = <TSchema extends RHFSchema>({
  schema,
  ...options
}: UseFormOptions<TSchema>) => {
  type TIn = z.input<TSchema>;

  // Bridge resolver typing across Zod/RHF/resolvers versions.
  const makeResolver = zodResolver as unknown as (
    s: z.ZodTypeAny
  ) => Resolver<TIn>;

  return useReactHookForm<TIn>({
    resolver: makeResolver(schema as z.ZodTypeAny),
    mode: "onBlur",
    ...options,
  });
};

// Optional helper: parsed/validated output type (useful if you coerce/transform)
export type FormOutput<TSchema extends RHFSchema> = z.output<TSchema>;
