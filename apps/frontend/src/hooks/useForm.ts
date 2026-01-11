/**
 * Custom form hook using React Hook Form and Zod
 */
import { useForm as useReactHookForm, UseFormProps, FieldValues } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ZodSchema } from 'zod';

export interface UseFormOptions<T extends FieldValues> extends Omit<UseFormProps<T>, 'resolver'> {
    schema: ZodSchema<T>;
}

export const useForm = <T extends FieldValues>({ schema, ...options }: UseFormOptions<T>) => {
    return useReactHookForm<T>({
        resolver: zodResolver(schema),
        mode: 'onBlur',
        ...options,
    });
};
