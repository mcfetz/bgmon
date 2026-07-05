import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';

/** @type {import('eslint').Linter.Config[]} */
export default [
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs['flat/recommended'],
	{
		languageOptions: {
			globals: {
				...globals.browser,
				...globals.node
			}
		}
	},
	{
		files: ['**/*.svelte'],
		languageOptions: {
			parserOptions: {
				parser: ts.parser
			}
		},
		settings: {
			svelte: {
				ignoreWarnings: ['a11y_label_has_associated_control', 'a11y_no_static_element_interactions']
			}
		},
		rules: {
			'svelte/valid-compile': 'off',
			'jsx-a11y/label-has-associated-control': 'off',
			'no-empty': 'off',
			'@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }]
		}
	},
	{
		ignores: ['dist/', '.svelte-kit/', 'node_modules/']
	}
];
