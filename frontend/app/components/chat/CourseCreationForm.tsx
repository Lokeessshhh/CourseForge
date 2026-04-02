'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import styles from './CourseCreationForm.module.css';

export interface FormField {
  name: string;
  type: 'text' | 'number' | 'select' | 'textarea';
  label: string;
  placeholder?: string;
  options?: Array<{ value: string; label: string }>;
  required: boolean;
  min?: number;
  max?: number;
  rows?: number;
}

export interface FormSchema {
  fields: FormField[];
  prefilled: Record<string, any>;
}

interface CourseCreationFormProps {
  schema: FormSchema;
  onSubmit: (data: Record<string, any>) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export default function CourseCreationForm({
  schema,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: CourseCreationFormProps) {
  const [formData, setFormData] = useState<Record<string, any>>({
    ...schema.prefilled,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleChange = (name: string, value: any) => {
    setFormData(prev => ({ ...prev, [name]: value }));
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};
    
    schema.fields.forEach(field => {
      if (field.required) {
        const value = formData[field.name];
        if (!value || (typeof value === 'string' && !value.trim())) {
          newErrors[field.name] = `${field.label} is required`;
        }
      }
      
      if (field.type === 'number' && formData[field.name]) {
        const num = Number(formData[field.name]);
        if (field.min !== undefined && num < field.min) {
          newErrors[field.name] = `Minimum value is ${field.min}`;
        }
        if (field.max !== undefined && num > field.max) {
          newErrors[field.name] = `Maximum value is ${field.max}`;
        }
      }
    });
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit(formData);
    }
  };

  const renderField = (field: FormField) => {
    const value = formData[field.name] || '';
    const error = errors[field.name];

    if (field.type === 'select') {
      return (
        <select
          className={`${styles.input} ${error ? styles.inputError : ''}`}
          value={value}
          onChange={(e) => handleChange(field.name, e.target.value)}
          disabled={isSubmitting}
        >
          <option value="">Select {field.label}</option>
          {field.options?.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      );
    }

    if (field.type === 'textarea') {
      return (
        <textarea
          className={`${styles.textarea} ${error ? styles.inputError : ''}`}
          placeholder={field.placeholder}
          value={value}
          onChange={(e) => handleChange(field.name, e.target.value)}
          disabled={isSubmitting}
          rows={field.rows || 3}
        />
      );
    }

    if (field.type === 'number') {
      return (
        <input
          type="number"
          className={`${styles.input} ${error ? styles.inputError : ''}`}
          placeholder={field.placeholder}
          value={value}
          onChange={(e) => handleChange(field.name, e.target.value)}
          disabled={isSubmitting}
          min={field.min}
          max={field.max}
        />
      );
    }

    return (
      <input
        type="text"
        className={`${styles.input} ${error ? styles.inputError : ''}`}
        placeholder={field.placeholder}
        value={value}
        onChange={(e) => handleChange(field.name, e.target.value)}
        disabled={isSubmitting}
      />
    );
  };

  return (
    <motion.div
      className={styles.formContainer}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
    >
      <div className={styles.formHeader}>
        <span className={styles.formIcon}>📚</span>
        <span className={styles.formTitle}>Complete Course Details</span>
      </div>

      <form onSubmit={handleSubmit} className={styles.form}>
        {schema.fields.map(field => (
          <div key={field.name} className={styles.field}>
            <label className={styles.label}>
              {field.label} {field.required && <span className={styles.required}>*</span>}
            </label>
            {renderField(field)}
            {errors[field.name] && <p className={styles.errorText}>{errors[field.name]}</p>}
          </div>
        ))}

        <div className={styles.formActions}>
          <button
            type="button"
            className={styles.cancelBtn}
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className={styles.submitBtn}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating...' : 'Create Course'}
          </button>
        </div>
      </form>
    </motion.div>
  );
}
