def validate_csv(df):
    required_columns = ['S. No.', 'Product Name', 'Input Image Urls']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    return True
