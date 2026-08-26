import { describe, expect, it } from 'vitest';
import { reportErrorMessage } from './report';

describe('reportErrorMessage', () => {
	it('maps report error codes to German messages', () => {
		expect(reportErrorMessage({ error: 'no_patient' }, 404)).toBe(
			'Für den Bericht ist kein Patient eingerichtet.'
		);
		expect(
			reportErrorMessage(
				{ error: 'multiple_patients', message: 'Report requires one patient' },
				409
			)
		).toBe('Der Bericht kann nur mit genau einem eingerichteten Patienten erstellt werden.');
		expect(reportErrorMessage({ error: 'future_date_not_allowed' }, 400)).toBe(
			'Der Berichtszeitraum darf keine zukünftigen Tage enthalten.'
		);
		expect(reportErrorMessage({ error: 'account deactivated' }, 401)).toBe(
			'Dieses Konto wurde deaktiviert.'
		);
		expect(reportErrorMessage({ error: 'invalid_date_format' }, 400)).toBe(
			'Bitte geben Sie die Daten im Format JJJJ-MM-TT an.'
		);
		expect(reportErrorMessage({ error: 'max_days' }, 400)).toBe(
			'Der Berichtszeitraum darf höchstens 90 Tage umfassen.'
		);
		expect(reportErrorMessage({ error: 'report_data_limit_exceeded' }, 400)).toBe(
			'Für diesen Berichtszeitraum liegen zu viele Daten vor. Bitte wählen Sie einen kürzeren Zeitraum.'
		);
		expect(reportErrorMessage({ error: 'rate_limit_exceeded' }, 429)).toBe(
			'Zu viele Berichte wurden angefordert. Bitte versuchen Sie es gleich noch einmal.'
		);
		expect(reportErrorMessage({ error: 'start_before_end' }, 400)).toBe(
			'Das Startdatum muss am oder vor dem Enddatum liegen.'
		);
		expect(reportErrorMessage({ error: 'invalid_date_range' }, 400)).toBe(
			'Der gewählte Berichtszeitraum wird nicht unterstützt.'
		);
	});

	it('maps legacy localized validation errors without exposing raw backend text', () => {
		expect(reportErrorMessage({ error: 'Ungültiges Datumsformat (YYYY-MM-DD)' }, 400)).toBe(
			'Bitte geben Sie die Daten im Format JJJJ-MM-TT an.'
		);
		expect(reportErrorMessage({ error: 'Maximal 90 Tage' }, 400)).toBe(
			'Der Berichtszeitraum darf höchstens 90 Tage umfassen.'
		);
		expect(reportErrorMessage({ error: 'Startdatum muss vor Enddatum liegen' }, 400)).toBe(
			'Das Startdatum muss am oder vor dem Enddatum liegen.'
		);
	});

	it('does not show an unlocalized backend message', () => {
		expect(reportErrorMessage({ message: 'Internal server error' }, 500)).toBe(
			'Bericht konnte nicht erstellt werden (HTTP 500).'
		);
		expect(reportErrorMessage({ error: 'Something unexpected happened' }, 500)).toBe(
			'Bericht konnte nicht erstellt werden (HTTP 500).'
		);
		expect(reportErrorMessage({ message: 'Patient must be selected' }, 400)).toBe(
			'Bericht konnte nicht erstellt werden (HTTP 400).'
		);
	});
});
