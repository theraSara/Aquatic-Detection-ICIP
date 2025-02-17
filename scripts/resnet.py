import pathlib
import cv2
import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from keras.models import Sequential, Model
from keras.applications import ResNet50
from keras.preprocessing.image import ImageDataGenerator
from keras.layers import Dense, BatchNormalization, Conv2D, Input, Flatten, GlobalAveragePooling2D
from keras.utils import to_categorical
from keras.optimizers import Adam
from sklearn.metrics import confusion_matrix, classification_report, precision_score, recall_score, f1_score, accuracy_score, ConfusionMatrixDisplay
from sklearn.model_selection import train_test_split
from data import X_train, X_val, y_train, y_val, X_test, y_test

# Data visualization
crack_sample = cv2.imread('dataset/MVI_Training_Datasets/Problem_2/Positive/00010.jpg')
nocrack_sample = cv2.imread('dataset/MVI_Training_Datasets/Problem_2/Negative/00007.jpg')
print(crack_sample.shape)
print(nocrack_sample.shape)

# GPU/TPU Setup
def setup_strategy():
    try:
        tpu = tf.distribute.cluster_resolver.TPUClusterResolver.connect()
        strategy = tf.distribute.TPUStrategy(tpu)
    except:
        strategy = tf.distribute.get_strategy()
    print("Number of replicas:", strategy.num_replicas_in_sync)
    return strategy

strategy = setup_strategy()
AUTOTUNE = tf.data.AUTOTUNE

data_directory = pathlib.Path('dataset/MVI_Training_Datasets/Problem_2/')
batch_size = 25 * strategy.num_replicas_in_sync
# Positive: Crack
# Negative: No Crack
class_names = ['Positive', 'Negative']
IMG_SIZE = (227, 227)

# Preprocessing Function
def preprocess_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Image at {image_path} could not be loaded.")
    img = cv2.resize(img, IMG_SIZE)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    gray = gray.astype('float32') / 255.0
    edges = cv2.Canny((gray * 255).astype(np.uint8), threshold1=50, threshold2=150)
    edges = cv2.GaussianBlur(edges, (5, 5), 0)
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    return edges


# Evaluation Function
def evaluate_model(y_true, y_pred_probs):
    y_pred_classes = np.argmax(y_pred_probs, axis=1)
    precision = precision_score(y_true, y_pred_classes, average='weighted')
    recall = recall_score(y_true, y_pred_classes, average='weighted')
    f1 = f1_score(y_true, y_pred_classes, average='weighted')
    accuracy = accuracy_score(y_true, y_pred_classes)
    return precision, recall, f1, accuracy


# IoU Computation Function
def compute_iou(y_true, y_pred):
    y_true_binary = (y_true == 1).astype(np.uint8)
    y_pred_binary = (y_pred == 1).astype(np.uint8)
    intersection = np.sum(y_true_binary & y_pred_binary)
    union = np.sum(y_true_binary) + np.sum(y_pred_binary) - intersection
    return intersection / union if union != 0 else 0


# Model Creation
def create_resnet_model():
    input_tensor = Input(shape=(227, 227, 1))
    base_model = ResNet50(weights='imagenet', include_top=False, input_tensor=input_tensor)
    x = base_model.output
    x = BatchNormalization()(x)
    x = GlobalAveragePooling2D()(x)
    x = Dense(256, activation='relu')(x)
    x = BatchNormalization()(x)
    predictions = Dense(2, activation='softmax')(x)
    model = Model(inputs=base_model.input, outputs=predictions)

    for layer in base_model.layers:
        layer.trainable = False
    return model

# Initialize and Compile Model
model = create_resnet_model()
model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])

# Model Training
model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=10, batch_size=32)

# Model Evaluation
test_loss, test_acc = model.evaluate(X_test, y_test)
print(f'Test accuracy: {test_acc}')

# Detailed Evaluation on Test Set
y_true = np.argmax(y_test, axis=1)
y_pred_probs = model.predict(X_test)
y_pred_classes = np.argmax(y_pred_probs, axis=1)
precision, recall, f1, accuracy = evaluate_model(y_true, y_pred_probs)
iou = compute_iou(y_true, y_pred_classes)

print(f'Precision: {precision:.4f}')
print(f'Recall: {recall:.4f}')
print(f'F1 Score: {f1:.4f}')
print(f'Accuracy: {accuracy:.4f}')
print(f'IoU: {iou:.4f}')

# Confusion Matrix and Classification Report
cm = confusion_matrix(y_true, y_pred_classes)
ConfusionMatrixDisplay(cm, display_labels=class_names).plot(cmap='Blues')
plt.title('Confusion Matrix')
plt.show()

print(classification_report(y_true, y_pred_classes, target_names=class_names))