from flask import Flask, render_template, request, send_from_directory
import csv
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

class People:
    def __init__(self, people_data):
        self.people_data = people_data

    def get_person_data(self, person_name):
        return self.people_data.get(person_name.lower())

def get_sales_percentages(sales_amount):
    if 500_000_000 <= sales_amount <= 1_500_000_000:
        return (5, 3, 10, 2)
    elif 1_500_000_000 < sales_amount <= 3_000_000_000:
        return (6, 4, 11, 4)
    elif 3_000_000_000 < sales_amount <= 5_000_000_000:
        return (7, 6, 12, 5)
    elif 5_000_000_000 <= sales_amount <= 8_000_000_000:
        return (8, 7, 14, 6)
    elif 8_000_000_000 <= sales_amount <= 10_000_000_000:
        return (9, 8, 21, 7)
    elif sales_amount > 10_000_000_000:
        return (10, 10, 22, 8)
    else:
        return (0, 0, 0, 0)

def parse_people_csv(file, logs):
    people_data = {}
    reader = csv.DictReader(file)
    headers = {header.strip().lower(): header.strip() for header in reader.fieldnames}
    print("Available columns in people CSV:", headers)
    
    rows = list(reader)
    if len(rows) < 4:
        raise KeyError("People CSV does not contain enough rows for salary and sales data")

    for person in headers.values():
        if person.lower() == 'stats':
            continue
        people_data[person.lower()] = {
            'salary': float(rows[0][person]),
            'sales': [
                float(rows[1][person]),
                float(rows[2][person]),
                float(rows[3][person])
            ]
        }
    
    print("Parsed People Data:", people_data)
    return people_data

def calculate_commissions(sales_file, people, logs):
    commissions = {}
    logs_by_month = {}
    adjustments = {}
    reader = csv.DictReader(sales_file)

    if 'SaleID' not in reader.fieldnames:
        generate_sale_id = True
    else:
        generate_sale_id = False

    role_labels = {
        'marketer': 'بازاریاب',
        'sales_manager': 'مدیر فروش',
        'senior_negotiator': 'فروشنده ارشد',
        'sales_coordinator': 'هماهنگ کننده'
    }

    for row_index, row in enumerate(reader):
        roles = {
            'marketer': row['Marketer'].strip().lower(),
            'sales_manager': row['SalesManager'].strip().lower(),
            'senior_negotiator': row['SeniorNegotiator'].strip().lower(),
            'sales_coordinator': row['SalesCoordinator'].strip().lower()
        }
        sale_amount = float(row['SaleAmount'])
        month = int(row['Month'])
        sale_id = row['SaleID'] if not generate_sale_id else f"sale_{row_index}"

        if month not in logs_by_month:
            logs_by_month[month] = {}
        if sale_id not in logs_by_month[month]:
            logs_by_month[month][sale_id] = {'amount': sale_amount, 'details': []}

        logs.append(f"✨ پردازش فروش برای ماه {month}:\nمبلغ فروش: {sale_amount:,.2f}")
        logs_by_month[month][sale_id]['details'].append({'index': 'شروع', 'details': f"مبلغ فروش: {sale_amount:,.2f}"})

        for role, person in roles.items():
            if person in people.people_data:
                person_data = people.get_person_data(person)
                monthly_sales = person_data['sales'][month - 1]  # Monthly sales for the respective month
                percentages = get_sales_percentages(monthly_sales)
                commission_rate = percentages[list(roles.keys()).index(role)]
                commission_amount = (commission_rate / 100) * sale_amount
                if (person, month) not in commissions:
                    commissions[(person, month)] = 0
                commissions[(person, month)] += commission_amount
                log_entry = {
                    'index': role_labels[role],  # Use Persian labels here
                    'details': f"{person.capitalize()} به عنوان {role_labels[role]}\n    فروش ماهانه: {monthly_sales:,.2f}\n    نرخ کمیسیون: {commission_rate}%\n    مبلغ کمیسیون: {commission_amount:,.2f}"
                }
                logs_by_month[month][sale_id]['details'].append(log_entry)

    for (person, month), total_commission in commissions.items():
        salary = people.get_person_data(person)['salary']
        if salary < 10:
            adjustment_rate = 0
        elif 10 <= salary < 100000000:
            adjustment_rate = 0.005
        elif 100000000 <= salary <= 150000000:
            adjustment_rate = 0.075
        else:
            adjustment_rate = 0.01
        adjustment = salary * adjustment_rate
        final_commission = total_commission - adjustment
        log_entry = {
            'index': 'تعدیلات',
            'details': f"{person.capitalize()} \n    کل کمیسیون: {total_commission:,.2f}\n    حقوق: {salary:,.2f}\n    نرخ کسر: {adjustment_rate * 100}%\n    کسر: {adjustment:,.2f}\n    کمیسیون نهایی: {final_commission:,.2f}"
        }
        if month not in adjustments:
            adjustments[month] = []
        adjustments[month].append(log_entry['details'])
        logs_by_month[month]['adjustments'] = [log_entry]
        commissions[(person, month)] = final_commission

    return commissions, logs_by_month, adjustments


def intcomma(value):
    return "{:,}".format(value)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.jinja_env.filters['intcomma'] = intcomma  # Register the filter

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    logs = []
    if 'people_file' not in request.files or 'sales_file' not in request.files:
        return "Both people and sales files are required"
    
    people_file = request.files['people_file']
    sales_file = request.files['sales_file']
    
    if people_file.filename == '' or sales_file.filename == '':
        return "Both files must be selected"
    
    if allowed_file(people_file.filename) and allowed_file(sales_file.filename):
        people_filename = secure_filename(people_file.filename)
        sales_filename = secure_filename(sales_file.filename)
        
        people_filepath = os.path.join(app.config['UPLOAD_FOLDER'], people_filename)
        sales_filepath = os.path.join(app.config['UPLOAD_FOLDER'], sales_filename)
        
        people_file.save(people_filepath)
        sales_file.save(sales_filepath)
        
        with open(people_filepath, 'r') as file:
            people_data = parse_people_csv(file, logs)
        
        people = People(people_data)
        
        with open(sales_filepath, 'r') as file:
            commissions, logs_by_month, adjustments = calculate_commissions(file, people, logs)
        
        months = sorted(set(month for _, month in commissions.keys()))
        results = {}
        for month in months:
            results[month] = {}
            for (person, m), commission in sorted(commissions.items()):
                if m == month:
                    formatted_person = person.capitalize()
                    formatted_commission = "{:,.2f}".format(commission)
                    results[month][formatted_person] = formatted_commission
        
        os.remove(people_filepath)
        os.remove(sales_filepath)
        
        return render_template('results.html', results=results, logs=logs, logs_by_month=logs_by_month, adjustments=adjustments)
    else:
        return "Invalid file type"

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory('static/csv', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
