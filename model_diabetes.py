import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# 1. Load the dataset
df = pd.read_csv('Dataset/Diabetes_Dataset.csv')

# 2. Separate input features (X) and target label (y)
X = df.drop(columns=['target'])
y = df['target']

# 3. Specify feature columns
num_cols = [
    'age',
    'bmi',
    'glucose_level',
    'blood_pressure',
    'insulin_level',
    'skin_thickness',
    'diabetes_pedigree',
]

cat_cols = [
    'gender',
    'family_history',
    'physical_activity',
]

# 4. Set up preprocessing (Scaling numbers + OneHot Encoding text)
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), num_cols),
        ('cat', OneHotEncoder(drop='first', handle_unknown='ignore'), cat_cols),
    ]
)

# 5. Create full Machine Learning pipeline
model_pipeline = Pipeline(
    steps=[
        ('preprocessor', preprocessor),
        (
            'classifier',
            RandomForestClassifier(n_estimators=100, random_state=42),
        ),
    ]
)

# 6. Split dataset into 80% Training and 20% Testing sets
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# 7. Train the model
model_pipeline.fit(X_train, y_train)

# 8. Evaluate on test set
y_pred = model_pipeline.predict(X_test)

print('--- Model Evaluation ---')
print('Accuracy Score:', accuracy_score(y_test, y_pred))
print('\nConfusion Matrix:\n', confusion_matrix(y_test, y_pred))
print('\nClassification Report:\n', classification_report(y_test, y_pred))

# 9. Save trained model pipeline for Flask backend
joblib.dump(model_pipeline, 'Models/diabetes_rf_model.pkl')
print('\nModel saved successfully as Models/diabetes_rf_model.pkl!')
