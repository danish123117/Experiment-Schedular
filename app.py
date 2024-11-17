from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from datetime import datetime, timedelta
import pandas as pd
import io

app = Flask(__name__)

def generate_time_options():
    """Generate time options in 15-minute intervals from 00:00 to 23:45."""
    times = []
    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            times.append(f"{hour:02d}:{minute:02d}")
    return times

experiment_data = {
    "trial_length": 60,
    "prep_time": 15,
    "default_start_time": "10:00",
    "default_end_time": "18:00",
    "exclude_lunch": True,
    "lunch_start": "12:00",
    "lunch_end": "12:30",
    "experiment_days": [],
    "custom_times": {}
}

@app.route('/', methods=['GET', 'POST'])
def index():
    time_options = generate_time_options()
    if request.method == 'POST':
        # Capture form data
        experiment_data["trial_length"] = int(request.form['trial_length'])
        experiment_data["prep_time"] = int(request.form['prep_time'])
        experiment_data["default_start_time"] = request.form['default_start_time']
        experiment_data["default_end_time"] = request.form['default_end_time']
        experiment_data["exclude_lunch"] = 'exclude_lunch' in request.form

        if not experiment_data["exclude_lunch"]:
            experiment_data["lunch_start"] = request.form['lunch_start']
            experiment_data["lunch_end"] = request.form['lunch_end']

        return redirect(url_for('select_days'))

    return render_template('index.html', data=experiment_data, time_options=time_options)

@app.route('/select_days', methods=['GET', 'POST'])
def select_days():
    if request.method == 'POST':
        selected_days = request.form['experiment_days']
        experiment_data["experiment_days"] = [
            datetime.strptime(day.strip(), '%Y-%m-%d') for day in selected_days.split(',')
        ]

        # Initialize custom times with default values
        experiment_data["custom_times"] = {
            day.strftime('%Y-%m-%d'): {
                "start": experiment_data["default_start_time"],
                "end": experiment_data["default_end_time"]
            }
            for day in experiment_data["experiment_days"]
        }
        return redirect(url_for('verify_schedule'))

    return render_template('select_days.html', data=experiment_data)

@app.route('/verify_schedule', methods=['GET', 'POST'])
def verify_schedule():
    time_options = generate_time_options()
    if request.method == 'POST':
        # Update custom times based on form inputs
        for day in experiment_data["experiment_days"]:
            day_str = day.strftime('%Y-%m-%d')
            experiment_data["custom_times"][day_str]["start"] = request.form[f'custom_start_{day_str}']
            experiment_data["custom_times"][day_str]["end"] = request.form[f'custom_end_{day_str}']

        # Generate the schedule
        schedule = []
        for day in experiment_data["experiment_days"]:
            day_str = day.strftime('%Y-%m-%d')
            start_time = datetime.strptime(experiment_data["custom_times"][day_str]["start"], '%H:%M')
            end_time = datetime.strptime(experiment_data["custom_times"][day_str]["end"], '%H:%M')
            lunch_start = datetime.strptime(experiment_data["lunch_start"], '%H:%M')
            lunch_end = datetime.strptime(experiment_data["lunch_end"], '%H:%M')
            current_time = start_time

            while current_time + timedelta(minutes=experiment_data["trial_length"]) <= end_time:
                # Handle lunch break
                if not experiment_data["exclude_lunch"] and lunch_start <= current_time < lunch_end:
                    schedule.append({
                        "Date": day_str,
                        "Slot": "Lunch",
                        "Trial Start": lunch_start.strftime('%H:%M'),
                        "Trial End": lunch_end.strftime('%H:%M')
                    })
                    current_time = lunch_end
                    continue

                # Add trial slots including preparation time
                trial_start = current_time
                trial_end = trial_start + timedelta(minutes=experiment_data["trial_length"] + experiment_data["prep_time"])
                schedule.append({
                    "Date": day_str,
                    "Slot": len(schedule) + 1,
                    "Trial Start": trial_start.strftime('%H:%M'),
                    "Trial End": trial_end.strftime('%H:%M')
                })
                current_time = trial_end  # Start next trial after this one ends

            # Add a blank row between days
            schedule.append({"Date": "", "Slot": "", "Trial Start": "", "Trial End": ""})

        # Remove the last blank row
        if schedule[-1] == {"Date": "", "Slot": "", "Trial Start": "", "Trial End": ""}:
            schedule.pop()

        # Create a DataFrame
        df = pd.DataFrame(schedule)

        # Create Excel with formatting
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Schedule')
            workbook = writer.book
            worksheet = writer.sheets['Schedule']

            # Header format
            header_format = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': 'powder blue',
                'border': 1
            })

            # Cell format with borders
            cell_format = workbook.add_format({
                'border': 1
            })

            # Apply header formatting
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Apply cell formatting
            for row in range(1, len(df) + 1):
                for col in range(len(df.columns)):
                    worksheet.write(row, col, df.iloc[row - 1, col], cell_format)

            # Adjust column widths
            worksheet.set_column('A:A', 15)
            worksheet.set_column('B:B', 10)
            worksheet.set_column('C:D', 15)

        output.seek(0)
        return send_file(output, as_attachment=True, download_name='experiment_schedule.xlsx')

    return render_template('verify_schedule.html', data=experiment_data, time_options=time_options)




if __name__ == '__main__':
    app.run(debug=True)

