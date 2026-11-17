def read_model(model_name: ModelName = Path(...)):
    if model_name is ModelName.alexnet:
        return {"message": "You selected alexnet"}
    elif model_name is ModelName.vgg16:
        return {"message": "You selected vgg16"}
    else:
        return {"message": "You selected resnet50"}